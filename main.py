"""
IGRIS AI Backend v6.1 (Groq + Gemini Vision) - SUPER FAST File Intelligence
============================================================================

Features:
  - Multi-API key rotation for Groq
  - Gemini Vision for actual image analysis (google-genai SDK v2.9+)
  - Async concurrent batch processing
  - Speed tier system
  - Parallel archive extraction
  - 100MB file limit
  - Rate limit aware retry with exponential backoff
  - Groq chat completions API (OpenAI-compatible)

Uses: groq SDK (pip install groq), google-genai (pip install google-genai)
Run: uvicorn main:app --host 0.0.0.0 --port 8000
"""

import os
import io
import json
import logging
import mimetypes
import zipfile
import random
import time
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config

# ---------------------------------------------------------------------------
# NEW: Google GenAI SDK (latest, replaces deprecated google-generativeai)
# ---------------------------------------------------------------------------
try:
    from google import genai
    from google.genai import types as genai_types
    from google.genai import errors as genai_errors
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logging.warning("google-genai not installed. Gemini vision will be unavailable. Run: pip install google-genai")

# ---------------------------------------------------------------------------
# HARDCODED GEMINI CONFIG — DO NOT TOUCH CONFIG.PY
# ---------------------------------------------------------------------------

GEMINI_API_KEY = "AQ.Ab8RN6KmJeyNp5oFoM0Q66NVloHvNMyevIs3u6wdFeZIfGfjbw"
GEMINI_MODEL = "gemini-flash-lite-latest"  # Fast vision model. Alt: gemini-2.5-pro for max quality
GEMINI_TIMEOUT = 45
GEMINI_MAX_CONCURRENT = 2
ENABLE_DETAILED_IMAGE_ANALYSIS = True  # Set False for faster, less detailed image analysis

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format=config.LOG_FORMAT,
)
logger = logging.getLogger("igris")

logger.info(
    f"IGRIS v6.1 (Groq + Gemini Vision) | Model: {config.GROQ_MODEL} | "
    f"Tier: {config.SPEED_TIER} | Keys: {len(config.GROQ_API_KEYS)} | "
    f"Concurrent: {config.MAX_CONCURRENT_FILES}"
)

# ---------------------------------------------------------------------------
# Thread pool for CPU-bound tasks
# ---------------------------------------------------------------------------

_executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_FILES)

# ---------------------------------------------------------------------------
# Groq client with multi-key rotation
# ---------------------------------------------------------------------------

_groq_clients: Dict[str, Any] = {}
_failed_keys: set = set()
_key_fail_counts: Dict[str, int] = {}
_key_error_log: Dict[str, List[str]] = {}
_key_lock = asyncio.Lock()


def _get_key_id(api_key: str) -> str:
    return api_key[:12] + "..." if len(api_key) > 15 else api_key


async def get_groq_client(force_new: bool = False):
    """Get a working Groq client with key rotation."""
    if config.MOCK_AI:
        return None
    if not config.GROQ_API_KEYS:
        raise RuntimeError("No GROQ_API_KEYS configured.")

    async with _key_lock:
        attempts = 0
        max_attempts = len(config.GROQ_API_KEYS)

        while attempts < max_attempts:
            key = config.get_next_api_key()
            key_id = _get_key_id(key)

            if key in _failed_keys and _key_fail_counts.get(key, 0) >= 3:
                attempts += 1
                continue

            if not force_new and key in _groq_clients:
                return _groq_clients[key]

            try:
                from groq import AsyncGroq
                client = AsyncGroq(api_key=key)
                _groq_clients[key] = client
                logger.info(f"Initialized Groq client with key: {key_id}")
                return client
            except Exception as exc:
                logger.error(f"Key {key_id} init failed: {exc}")
                _key_fail_counts[key] = _key_fail_counts.get(key, 0) + 1
                if _key_fail_counts[key] >= 3:
                    _failed_keys.add(key)
                attempts += 1

        raise RuntimeError("All Groq API keys failed to initialize.")


async def mark_key_failed(api_key: str, reason: str = "unknown"):
    """Mark a key as failed with reason tracking."""
    async with _key_lock:
        _key_fail_counts[api_key] = _key_fail_counts.get(api_key, 0) + 1
        if api_key not in _key_error_log:
            _key_error_log[api_key] = []
        _key_error_log[api_key].append(reason[:200])

        if _key_fail_counts[api_key] >= 3:
            _failed_keys.add(api_key)
            logger.warning(f"Key {_get_key_id(api_key)} PERMANENTLY blacklisted after 3 failures ({reason})")
        else:
            logger.warning(f"Key {_get_key_id(api_key)} failure {_key_fail_counts[api_key]}/3 ({reason})")


def _get_client_key(client) -> str:
    for key, cached in _groq_clients.items():
        if cached is client:
            return key
    return ""

# ---------------------------------------------------------------------------
# GEMINI VISION CLIENT — Hardcoded, no config.py dependency
# ---------------------------------------------------------------------------

_gemini_client: Optional[Any] = None
_gemini_lock = asyncio.Lock()
_gemini_semaphore = asyncio.Semaphore(GEMINI_MAX_CONCURRENT)
_gemini_failed = False


async def _init_gemini_client() -> Optional[Any]:
    """Initialize Gemini client with hardcoded key. Returns None on failure."""
    global _gemini_client, _gemini_failed
    
    if _gemini_failed:
        return None
    if not _GENAI_AVAILABLE:
        logger.warning("google-genai SDK not available. Install with: pip install google-genai")
        return None
    
    async with _gemini_lock:
        if _gemini_client is not None:
            return _gemini_client
        
        try:
            # New SDK pattern: genai.Client(api_key=...)
            client = genai.Client(api_key=GEMINI_API_KEY)
            _gemini_client = client
            logger.info(f"Gemini client initialized | Model: {GEMINI_MODEL}")
            return client
        except Exception as exc:
            logger.error(f"Gemini client init failed: {exc}")
            _gemini_failed = True
            return None


def _get_gemini_prompt(detailed: bool) -> str:
    """Build the vision prompt for Gemini."""
    if detailed:
        return (
            "Analyze this image in extreme detail. You are a computer vision expert. "
            "Return ONLY a valid JSON object with these exact keys and no markdown:\n"
            "{\n"
            '  "scene_description": "detailed description of what is happening in the image",\n'
            '  "objects_detected": ["list", "of", "detected", "objects"],\n'
            '  "text_ocr": "any text visible in the image, transcribed exactly",\n'
            '  "ui_interpretation": "if this is a UI/screenshot, describe the interface elements",\n'
            '  "colors_dominant": ["#hexcolor1", "#hexcolor2"],\n'
            '  "composition": "describe the visual composition, framing, perspective",\n'
            '  "mood_atmosphere": "describe the mood, lighting, atmosphere",\n'
            '  "technical_quality": "assess image quality, resolution, artifacts, blur",\n'
            '  "safety_flags": ["any concerning content flags or empty array"]\n'
            "}"
        )
    else:
        return (
            "Describe this image concisely. Return ONLY valid JSON with no markdown:\n"
            "{\n"
            '  "description": "brief description",\n'
            '  "objects": ["key", "objects"],\n'
            '  "text": "any visible text",\n'
            '  "insights": ["notable observation"]\n'
            "}"
        )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ImageAnalysisDetail(BaseModel):
    scene_description: str = ""
    objects_detected: List[str] = []
    text_ocr: str = ""
    ui_interpretation: str = ""
    colors_dominant: List[str] = []
    composition: str = ""
    mood_atmosphere: str = ""
    technical_quality: str = ""
    safety_flags: List[str] = []


class AnalysisBlock(BaseModel):
    description: str = ""
    key_points: List[str] = []
    objects: List[str] = []
    text: str = ""
    insights: List[str] = []
    image_details: Optional[ImageAnalysisDetail] = None
    archive_contents: List[Dict[str, Any]] = []
    archive_summary: str = ""


class MetaBlock(BaseModel):
    filename: str
    size: int
    mime_type: str
    extracted_files: int = 0
    processing_time_ms: float = 0.0


class SingleAnalyzeResponse(BaseModel):
    file_type: str
    summary: str
    analysis: AnalysisBlock
    meta: MetaBlock


class BatchAnalyzeResponse(BaseModel):
    results: List[SingleAnalyzeResponse]
    total_files: int
    successful: int
    failed: int
    total_time_ms: float


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="IGRIS AI Backend",
    description="SUPER FAST Unified File Intelligence API v6.1 (Groq + Gemini Vision)",
    version="6.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=config.CORS_ALLOW_METHODS,
    allow_headers=config.CORS_ALLOW_HEADERS,
)


@app.get("/")
def root():
    return {
        "service": "IGRIS AI Backend",
        "version": "6.1.0",
        "status": "online",
        "mock_mode": config.MOCK_AI,
        "speed_tier": config.SPEED_TIER,
        "model": config.GROQ_MODEL,
        "api_keys_loaded": len(config.GROQ_API_KEYS),
        "api_keys_failed": len(_failed_keys),
        "gemini_available": _GENAI_AVAILABLE and not _gemini_failed,
        "gemini_model": GEMINI_MODEL if _GENAI_AVAILABLE else None,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mock_mode": config.MOCK_AI,
        "model": config.GROQ_MODEL,
        "tier": config.SPEED_TIER,
        "api_keys_available": len(config.GROQ_API_KEYS),
        "api_keys_failed": len(_failed_keys),
        "api_keys_fail_counts": {k[:8]+"...": v for k, v in _key_fail_counts.items()},
        "gemini_available": _GENAI_AVAILABLE and not _gemini_failed,
        "gemini_model": GEMINI_MODEL if _GENAI_AVAILABLE else None,
    }


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".ico"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".rtf", ".doc", ".odt"}
CODE_EXTENSIONS = {
    ".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".py", ".css", ".scss",
    ".sass", ".less", ".json", ".java", ".c", ".cpp", ".h", ".hpp", ".go", ".rs", ".rb",
    ".php", ".sh", ".bash", ".zsh", ".yml", ".yaml", ".sql", ".swift", ".kt", ".kts",
    ".cs", ".vb", ".fs", ".scala", ".clj", ".cljs", ".erl", ".ex", ".exs", ".lua",
    ".pl", ".pm", ".r", ".m", ".mm", ".dart", ".groovy", ".gradle", ".xml", ".svg",
    ".dockerfile", ".makefile", ".cmake", ".toml", ".ini", ".cfg", ".conf", ".properties",
    ".log", ".csv", ".tsv", ".ipynb", ".vue", ".svelte", ".astro", ".sol", ".tf", ".hcl",
    ".asm", ".s", ".v", ".sv", ".vhd", ".vhdl", ".pas", ".dpr", ".lpr", ".nim", ".nims",
    ".cr", ".crystal", ".d", ".di", ".gd", ".tscn", ".gdscript", ".wren", ".wgsl",
    ".glsl", ".hlsl", ".vert", ".frag", ".comp", ".geom", ".tesc", ".tese",
}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar"}


def detect_file_type(filename: str, mime_type: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return "image"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in ARCHIVE_EXTENSIONS or mime_type in (
        "application/zip", "application/x-zip-compressed",
        "application/x-tar", "application/gzip",
        "application/x-7z-compressed", "application/x-rar-compressed",
    ):
        return "archive"
    return "unknown"


# ---------------------------------------------------------------------------
# Text extraction (CPU-bound, thread pool)
# ---------------------------------------------------------------------------

def _extract_pdf(raw: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(io.BytesIO(raw)) or ""
    except Exception:
        return ""


def _extract_docx(raw: bytes) -> str:
    try:
        import docx
        return "\n".join(p.text for p in docx.Document(io.BytesIO(raw)).paragraphs)
    except Exception:
        return ""


def _extract_plain(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return ""


def extract_document_text(filename: str, raw: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        return _extract_pdf(raw)
    if ext == ".docx":
        return _extract_docx(raw)
    return _extract_plain(raw)


# ---------------------------------------------------------------------------
# ZIP extraction (async wrapper for thread pool)
# ---------------------------------------------------------------------------

@dataclass
class ExtractedFile:
    filename: str
    relative_path: str
    size: int
    raw: bytes
    file_type: str
    mime_type: str


def _extract_zip_sync(raw: bytes) -> List[ExtractedFile]:
    extracted = []
    total_size = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.filename.startswith("__MACOSX/") or os.path.basename(info.filename).startswith("."):
                    continue
                if len(extracted) >= config.MAX_ARCHIVE_FILES:
                    break
                try:
                    file_raw = zf.read(info.filename)
                    total_size += len(file_raw)
                    if total_size > config.MAX_ARCHIVE_TOTAL_SIZE:
                        break
                    mime = mimetypes.guess_type(info.filename)[0] or "application/octet-stream"
                    ftype = detect_file_type(info.filename, mime)
                    extracted.append(ExtractedFile(
                        filename=os.path.basename(info.filename),
                        relative_path=info.filename,
                        size=len(file_raw), raw=file_raw,
                        file_type=ftype, mime_type=mime,
                    ))
                except Exception:
                    continue
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid ZIP file format")
    return extracted


async def extract_zip_contents(raw: bytes) -> List[ExtractedFile]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _extract_zip_sync, raw)


# ---------------------------------------------------------------------------
# Groq AI call with retry + rotation + timeout
# ---------------------------------------------------------------------------

async def _call_groq_with_retry(messages: List[Dict[str, str]], temperature: float = 0.3) -> Any:
    """Call Groq chat.completions with retry, key rotation, and rate limit protection."""
    last_error = None
    max_retries = min(len(config.GROQ_API_KEYS) if config.GROQ_API_KEYS else 1, 4)

    for attempt in range(max_retries):
        client = None
        key = None
        try:
            client = await get_groq_client(force_new=(attempt > 0))
            key = _get_client_key(client)
            key_id = _get_key_id(key) if key else "unknown"

            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=config.GROQ_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=4096,
                ),
                timeout=config.AI_TIMEOUT
            )

            # Success! Reset fail count for this key
            if key and key in _key_fail_counts:
                _key_fail_counts[key] = max(0, _key_fail_counts[key] - 1)

            return response

        except asyncio.TimeoutError:
            logger.warning(f"Groq timeout (attempt {attempt + 1}/{max_retries}) - NOT blacklisting")
            last_error = "Timeout"
            continue

        except Exception as exc:
            error_str = str(exc).lower()
            last_error = exc

            # Categorize the error
            if "429" in error_str or "rate limit" in error_str:
                logger.warning(f"Rate limit on key {key_id} - backing off")
                if key:
                    await mark_key_failed(key, "rate_limit")
                await asyncio.sleep(2 ** attempt)
                continue

            elif any(x in error_str for x in ["401", "unauthorized", "invalid api key", "authentication"]):
                logger.error(f"AUTH ERROR on key {key_id}: {exc}")
                if key:
                    await mark_key_failed(key, "auth_invalid")
                if config.AGGRESSIVE_RETRY:
                    continue

            elif any(x in error_str for x in ["403", "permission denied", "forbidden"]):
                logger.error(f"PERMISSION ERROR on key {key_id}: {exc}")
                if key:
                    await mark_key_failed(key, "permission_denied")
                if config.AGGRESSIVE_RETRY:
                    continue

            elif "model" in error_str and ("not found" in error_str or "not supported" in error_str or "decommissioned" in error_str):
                logger.error(f"MODEL ERROR: {config.GROQ_MODEL} not found - {exc}")
                raise RuntimeError(f"Model '{config.GROQ_MODEL}' not found. Check console.groq.com/docs/models")

            else:
                logger.error(f"API ERROR on key {key_id}: {exc}")
                if key:
                    await mark_key_failed(key, f"api_error: {error_str[:50]}")
                if config.AGGRESSIVE_RETRY:
                    continue

            raise

    raise RuntimeError(f"All Groq API keys exhausted. Last error: {last_error}")


# ---------------------------------------------------------------------------
# AI Pipelines
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        return {"summary": text[:500]}


def _get_image_metadata(raw: bytes, mime_type: str) -> Dict[str, Any]:
    """Extract basic metadata from image bytes since Groq doesn't support vision."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        return {
            "format": img.format,
            "mode": img.mode,
            "width": img.width,
            "height": img.height,
            "size_bytes": len(raw),
            "mime_type": mime_type,
        }
    except Exception:
        return {"size_bytes": len(raw), "mime_type": mime_type}


def _image_to_base64(raw: bytes, mime_type: str) -> str:
    """Convert image to base64 data URI for potential vision support."""
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


# =============================================================================
# GEMINI VISION PIPELINE — The Real Deal
# =============================================================================

async def _call_gemini_vision(filename: str, raw: bytes, mime_type: str, detailed: bool) -> Optional[Dict[str, Any]]:
    """
    Call Gemini vision using the latest google-genai SDK.
    Returns parsed dict or None on failure (falls back to Groq).
    """
    if not _GENAI_AVAILABLE:
        return None
    
    client = await _init_gemini_client()
    if not client:
        return None
    
    async with _gemini_semaphore:
        try:
            prompt = _get_gemini_prompt(detailed)
            
            # New SDK v2.9+ pattern: types.Part.from_bytes(data=..., mime_type=...)
            # contents can be a mixed list of text and parts
            contents = [
                prompt,
                genai_types.Part.from_bytes(data=raw, mime_type=mime_type),
            ]
            
            # Use async client via client.aio.models.generate_content
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=4096,
                    ),
                ),
                timeout=GEMINI_TIMEOUT,
            )
            
            text = response.text if hasattr(response, 'text') else str(response)
            parsed = _parse_json_response(text)
            
            if detailed:
                return {
                    "summary": (parsed.get("scene_description", "")[:280] or f"Image: {filename}"),
                    "description": parsed.get("scene_description", ""),
                    "key_points": [],
                    "objects": parsed.get("objects_detected", []),
                    "text": parsed.get("text_ocr", ""),
                    "insights": [
                        f"UI: {parsed.get('ui_interpretation', 'N/A')}",
                        f"Mood: {parsed.get('mood_atmosphere', 'N/A')}",
                        f"Tech: {parsed.get('technical_quality', 'N/A')}",
                    ] if any([parsed.get("ui_interpretation"), parsed.get("mood_atmosphere"), parsed.get("technical_quality")]) else [],
                    "image_details": {
                        "scene_description": parsed.get("scene_description", ""),
                        "objects_detected": parsed.get("objects_detected", []),
                        "text_ocr": parsed.get("text_ocr", ""),
                        "ui_interpretation": parsed.get("ui_interpretation", ""),
                        "colors_dominant": parsed.get("colors_dominant", []),
                        "composition": parsed.get("composition", ""),
                        "mood_atmosphere": parsed.get("mood_atmosphere", ""),
                        "technical_quality": parsed.get("technical_quality", ""),
                        "safety_flags": parsed.get("safety_flags", []),
                    },
                }
            else:
                return {
                    "summary": parsed.get("description", "")[:280],
                    "description": parsed.get("description", ""),
                    "key_points": [],
                    "objects": parsed.get("objects", []),
                    "text": parsed.get("text", ""),
                    "insights": parsed.get("insights", []),
                }
                
        except asyncio.TimeoutError:
            logger.warning("Gemini vision timeout, falling back to Groq metadata")
            return None
        except Exception as exc:
            error_str = str(exc).lower()
            logger.error(f"Gemini vision error: {exc}")
            
            # Check for auth/rate limit issues
            if any(x in error_str for x in ["429", "rate limit", "quota", "403", "401", "invalid api key", "permission"]):
                global _gemini_failed
                _gemini_failed = True
                logger.error("Gemini key permanently failed. Will use Groq fallback for images.")
            
            return None


async def run_image_pipeline(filename: str, raw: bytes, mime_type: str) -> Dict[str, Any]:
    if config.MOCK_AI:
        return {
            "summary": "[MOCK] Image analyzed",
            "description": "[MOCK] Placeholder",
            "key_points": [],
            "objects": ["[mock] object"],
            "text": "[MOCK] OCR",
            "insights": ["[MOCK] insight"],
            "image_details": {
                "scene_description": "[MOCK] scene",
                "objects_detected": ["[mock] obj"],
                "text_ocr": "[MOCK] text",
                "ui_interpretation": "[MOCK] UI",
                "colors_dominant": ["#000000"],
                "composition": "[MOCK] comp",
                "mood_atmosphere": "[MOCK] mood",
                "technical_quality": "[MOCK] tech",
                "safety_flags": [],
            }
        }

    # Try Gemini Vision FIRST — actual image understanding
    detailed = ENABLE_DETAILED_IMAGE_ANALYSIS
    gemini_result = await _call_gemini_vision(filename, raw, mime_type, detailed)
    if gemini_result is not None:
        logger.info(f"Gemini vision success for {filename}")
        return gemini_result
    
    # FALLBACK: Groq metadata-only analysis (original behavior)
    logger.info(f"Falling back to Groq metadata analysis for {filename}")
    metadata = _get_image_metadata(raw, mime_type)

    if detailed:
        prompt = (
            f"I have an image file named '{filename}' with these properties:\n"
            f"- Format: {metadata.get('format', 'unknown')}\n"
            f"- Dimensions: {metadata.get('width', '?')}x{metadata.get('height', '?')}\n"
            f"- Mode: {metadata.get('mode', 'unknown')}\n"
            f"- Size: {metadata.get('size_bytes', 0)} bytes\n"
            f"- MIME: {metadata.get('mime_type', 'unknown')}\n\n"
            "Since I cannot see the actual image, provide a GENERIC but detailed analysis template. "
            "Respond ONLY as JSON with keys: scene_description, objects_detected, text_ocr, "
            "ui_interpretation, colors_dominant, composition, mood_atmosphere, technical_quality, safety_flags. "
            "No markdown, no preamble."
        )
    else:
        prompt = (
            f"I have an image file named '{filename}' ({metadata.get('width', '?')}x{metadata.get('height', '?')}, "
            f"{metadata.get('format', 'unknown')}). Provide JSON with: description, objects (array), "
            "text (string), insights (array). No markdown."
        )

    messages = [{"role": "user", "content": prompt}]
    response = await _call_groq_with_retry(messages)
    parsed = _parse_json_response(response.choices[0].message.content)

    if detailed:
        return {
            "summary": (parsed.get("scene_description", "")[:280] or f"Image: {filename}"),
            "description": parsed.get("scene_description", ""),
            "key_points": [],
            "objects": parsed.get("objects_detected", []),
            "text": parsed.get("text_ocr", ""),
            "insights": [
                f"UI: {parsed.get('ui_interpretation', 'N/A')}",
                f"Mood: {parsed.get('mood_atmosphere', 'N/A')}",
                f"Tech: {parsed.get('technical_quality', 'N/A')}",
            ] if any([parsed.get("ui_interpretation"), parsed.get("mood_atmosphere"), parsed.get("technical_quality")]) else [],
            "image_details": {
                "scene_description": parsed.get("scene_description", ""),
                "objects_detected": parsed.get("objects_detected", []),
                "text_ocr": parsed.get("text_ocr", ""),
                "ui_interpretation": parsed.get("ui_interpretation", ""),
                "colors_dominant": parsed.get("colors_dominant", []),
                "composition": parsed.get("composition", ""),
                "mood_atmosphere": parsed.get("mood_atmosphere", ""),
                "technical_quality": parsed.get("technical_quality", ""),
                "safety_flags": parsed.get("safety_flags", []),
            },
        }
    else:
        return {
            "summary": parsed.get("description", "")[:280],
            "description": parsed.get("description", ""),
            "key_points": [],
            "objects": parsed.get("objects", []),
            "text": parsed.get("text", ""),
            "insights": parsed.get("insights", []),
        }


async def run_document_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    extracted_text = extract_document_text(filename, raw)

    if config.MOCK_AI:
        return {
            "summary": "[MOCK] Document summarized",
            "description": "",
            "key_points": ["[mock] point 1", "[mock] point 2"],
            "objects": [],
            "text": extracted_text[:2000],
            "insights": ["[MOCK] insight"],
        }

    prompt = (
        "Summarize this document. Return JSON with: summary, key_points (array), insights (array). "
        f"No markdown.\n\nDOCUMENT:\n{extracted_text[:config.MAX_TEXT_LENGTH]}"
    )

    messages = [{"role": "user", "content": prompt}]
    response = await _call_groq_with_retry(messages)
    parsed = _parse_json_response(response.choices[0].message.content)

    return {
        "summary": parsed.get("summary", ""),
        "description": "",
        "key_points": parsed.get("key_points", []),
        "objects": [],
        "text": extracted_text[:2000],
        "insights": parsed.get("insights", []),
    }


async def run_code_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    code_text = _extract_plain(raw)
    ext = os.path.splitext(filename.lower())[1].lstrip(".")

    if config.MOCK_AI:
        return {
            "summary": f"[MOCK] {ext} code",
            "description": f"[MOCK] lang: {ext}",
            "key_points": ["[mock] no bugs"],
            "objects": [],
            "text": code_text[:2000],
            "insights": ["[MOCK] add comments"],
        }

    if config.ENABLE_SECURITY_SCAN:
        prompt = (
            f"Review this .{ext} code. Return JSON: summary, bugs (array), "
            f"security_issues (array), improvements (array). No markdown.\n\nCODE:\n{code_text[:config.MAX_TEXT_LENGTH]}"
        )
    else:
        prompt = (
            f"Review this .{ext} code. Return JSON: summary, bugs (array), improvements (array). "
            f"No markdown.\n\nCODE:\n{code_text[:config.MAX_TEXT_LENGTH]}"
        )

    messages = [{"role": "user", "content": prompt}]
    response = await _call_groq_with_retry(messages)
    parsed = _parse_json_response(response.choices[0].message.content)

    key_points = [f"[bug] {b}" for b in parsed.get("bugs", [])]
    if config.ENABLE_SECURITY_SCAN:
        key_points += [f"[security] {s}" for s in parsed.get("security_issues", [])]

    return {
        "summary": parsed.get("summary", ""),
        "description": f"Detected: {ext}",
        "key_points": key_points,
        "objects": [],
        "text": code_text[:2000],
        "insights": parsed.get("improvements", []),
    }


async def run_archive_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    if not config.ENABLE_ARCHIVE_PROCESSING:
        return {
            "summary": "Archive processing disabled",
            "description": "", "key_points": ["Disabled"],
            "objects": [], "text": "",
            "insights": ["Enable in config"],
            "archive_contents": [], "archive_summary": "",
        }

    extracted_files = await extract_zip_contents(raw)
    total_files = len(extracted_files)

    if total_files == 0:
        return {
            "summary": "Empty ZIP", "description": "",
            "key_points": ["No files"], "objects": [], "text": "",
            "insights": ["Empty archive"],
            "archive_contents": [], "archive_summary": "Empty",
        }

    archive_analyses = []
    file_type_counts = {"image": 0, "document": 0, "code": 0, "unknown": 0}

    for file_info in extracted_files:
        file_type_counts[file_info.file_type] = file_type_counts.get(file_info.file_type, 0) + 1
        if config.MOCK_AI:
            archive_analyses.append({
                "filename": file_info.filename,
                "relative_path": file_info.relative_path,
                "size": file_info.size,
                "file_type": file_info.file_type,
                "mime_type": file_info.mime_type,
                "analysis": {"summary": f"[MOCK] {file_info.file_type}", "status": "mock"},
            })
        else:
            archive_analyses.append(await analyze_archive_file(file_info))

    summary_parts = [f"Archive: {total_files} files"]
    for ftype, count in file_type_counts.items():
        if count > 0:
            summary_parts.append(f"  {count} {ftype}")
    archive_summary = "\n".join(summary_parts)

    if not config.MOCK_AI and total_files > 0:
        try:
            overview = []
            for item in archive_analyses[:20]:
                overview.append(f"File: {item['filename']} ({item['file_type']})\nSummary: {item['analysis'].get('summary', 'N/A')[:200]}")

            prompt = (
                "Analyze this ZIP archive. Return JSON: purpose, patterns, security_concerns, next_steps. "
                f"No markdown.\n\n{'\n---\n'.join(overview)}"
            )
            messages = [{"role": "user", "content": prompt}]
            response = await _call_groq_with_retry(messages)
            parsed = _parse_json_response(response.choices[0].message.content)
            archive_summary += f"\n\nAI: {parsed.get('purpose', 'N/A')}"
        except Exception as exc:
            logger.warning(f"Archive AI summary failed: {exc}")

    return {
        "summary": f"Archive: {total_files} files processed",
        "description": "",
        "key_points": [f"Total: {total_files}", f"Images: {file_type_counts['image']}",
                       f"Docs: {file_type_counts['document']}", f"Code: {file_type_counts['code']}"],
        "objects": [], "text": "",
        "insights": [archive_summary],
        "archive_contents": archive_analyses,
        "archive_summary": archive_summary,
    }


async def analyze_archive_file(file_info: ExtractedFile) -> Dict[str, Any]:
    result = {
        "filename": file_info.filename,
        "relative_path": file_info.relative_path,
        "size": file_info.size,
        "file_type": file_info.file_type,
        "mime_type": file_info.mime_type,
        "analysis": {},
    }
    try:
        if file_info.file_type == "image":
            img = await run_image_pipeline(file_info.filename, file_info.raw, file_info.mime_type)
            result["analysis"] = {"summary": img.get("summary", ""), "description": img.get("description", ""),
                                   "objects": img.get("objects", []), "text": img.get("text", "")}
        elif file_info.file_type == "document":
            doc = await run_document_pipeline(file_info.filename, file_info.raw)
            result["analysis"] = {"summary": doc.get("summary", ""), "key_points": doc.get("key_points", []),
                                   "text_preview": doc.get("text", "")[:500]}
        elif file_info.file_type == "code":
            code = await run_code_pipeline(file_info.filename, file_info.raw)
            result["analysis"] = {"summary": code.get("summary", ""), "key_points": code.get("key_points", []),
                                   "language": code.get("description", "")}
        else:
            text = _extract_plain(file_info.raw)
            result["analysis"] = {"summary": "Unknown - text extracted" if text.strip() else "Binary file",
                                   "text_preview": text[:500] if text.strip() else ""}
    except Exception as exc:
        result["analysis"] = {"error": str(exc), "summary": "Failed"}
    return result


async def run_unknown_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    text = _extract_plain(raw)
    has_text = bool(text.strip())
    return {
        "summary": "Unknown file - text extracted" if has_text else "Unknown - no readable text",
        "description": "", "key_points": [], "objects": [],
        "text": text[:2000] if has_text else "",
        "insights": ["Unsupported file type"],
    }


# ---------------------------------------------------------------------------
# Core analysis (async with timing)
# ---------------------------------------------------------------------------

async def analyze_single_file(file: UploadFile) -> SingleAnalyzeResponse:
    start = time.time()

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")

    raw = await file.read()
    size = len(raw)

    if size > config.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Max {config.MAX_FILE_SIZE / (1024*1024):.0f}MB")

    mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    file_type = detect_file_type(file.filename, mime_type)

    logger.info(f"Processing '{file.filename}' ({size}b, {file_type})")

    try:
        if file_type == "image":
            result = await run_image_pipeline(file.filename, raw, mime_type)
        elif file_type == "document":
            result = await run_document_pipeline(file.filename, raw)
        elif file_type == "code":
            result = await run_code_pipeline(file.filename, raw)
        elif file_type == "archive":
            result = await run_archive_pipeline(file.filename, raw)
        else:
            result = await run_unknown_pipeline(file.filename, raw)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Analysis error")
        raise HTTPException(status_code=500, detail=f"Failed: {exc}")

    elapsed = (time.time() - start) * 1000

    return SingleAnalyzeResponse(
        file_type=file_type,
        summary=result.get("summary", ""),
        analysis=AnalysisBlock(
            description=result.get("description", ""),
            key_points=result.get("key_points", []),
            objects=result.get("objects", []),
            text=result.get("text", ""),
            insights=result.get("insights", []),
            image_details=result.get("image_details"),
            archive_contents=result.get("archive_contents", []),
            archive_summary=result.get("archive_summary", ""),
        ),
        meta=MetaBlock(
            filename=file.filename,
            size=size,
            mime_type=mime_type,
            extracted_files=len(result.get("archive_contents", [])),
            processing_time_ms=round(elapsed, 2),
        ),
    )


# ---------------------------------------------------------------------------
# Semaphore for concurrent control
# ---------------------------------------------------------------------------

_analysis_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_FILES)


async def analyze_single_file_limited(file: UploadFile) -> SingleAnalyzeResponse:
    async with _analysis_semaphore:
        return await analyze_single_file(file)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=SingleAnalyzeResponse)
async def analyze(file: UploadFile = File(...)):
    """Analyze a single file."""
    response = await analyze_single_file(file)
    return JSONResponse(content=response.model_dump())


@app.post("/analyze/batch", response_model=BatchAnalyzeResponse)
async def analyze_batch(files: List[UploadFile] = File(...)):
    """Analyze multiple files concurrently."""
    start = time.time()

    tasks = [analyze_single_file_limited(file) for file in files]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    successful = 0
    failed = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failed += 1
            fname = files[i].filename if i < len(files) else "unknown"
            processed.append(SingleAnalyzeResponse(
                file_type="error",
                summary=f"Error: {str(result)}",
                analysis=AnalysisBlock(insights=[f"Failed: {str(result)}"]),
                meta=MetaBlock(filename=fname, size=0, mime_type="error"),
            ))
        else:
            successful += 1
            processed.append(result)

    total_time = (time.time() - start) * 1000

    return JSONResponse(content=BatchAnalyzeResponse(
        results=processed,
        total_files=len(files),
        successful=successful,
        failed=failed,
        total_time_ms=round(total_time, 2),
    ).model_dump())
