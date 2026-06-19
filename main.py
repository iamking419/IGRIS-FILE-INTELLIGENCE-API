"""
IGRIS AI Backend — Unified File Intelligence API v2.0
=====================================================

Single endpoint (POST /analyze) that accepts any file, detects its type,
routes it to the correct processing pipeline, and returns structured JSON analysis.

NEW in v2.0:
  - Centralized config.py instead of scattered env vars
  - ZIP archive recursive processing
  - Enhanced image analysis with detailed scene understanding
  - Real Gemini AI integration (mock mode still available for testing)

Run locally:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

import os
import io
import json
import logging
import mimetypes
import zipfile
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import centralized config
import config

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format=config.LOG_FORMAT,
)
logger = logging.getLogger("igris")

logger.info(f"Startup config -> MOCK_AI={config.MOCK_AI} | GEMINI_MODEL={config.GEMINI_MODEL}")

# ---------------------------------------------------------------------------
# Gemini client (lazy import so the app still runs without the SDK installed
# while in mock mode)
# ---------------------------------------------------------------------------

_gemini_client = None


def get_gemini_client():
    """Lazily construct and cache the Gemini client. Only called in live mode."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai SDK is not installed. Run `pip install google-genai`."
        ) from exc

    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set but MOCK_AI is false.")

    _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _gemini_client


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


class AnalyzeResponse(BaseModel):
    file_type: str
    summary: str
    analysis: AnalysisBlock
    meta: MetaBlock


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="IGRIS AI Backend",
    description="Unified File Intelligence API — upload anything, get structured AI analysis.",
    version="2.0.0",
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
        "version": "2.0.0",
        "status": "online",
        "mock_mode": config.MOCK_AI,
        "model": config.GEMINI_MODEL,
        "features": [
            "image_analysis",
            "document_analysis",
            "code_analysis",
            "zip_processing",
        ],
        "endpoint": "POST /analyze",
    }


@app.get("/health")
def health():
    return {"status": "ok", "mock_mode": config.MOCK_AI, "model": config.GEMINI_MODEL}


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
    """Classify a file into image | document | code | archive | unknown."""
    ext = os.path.splitext(filename.lower())[1]

    if ext in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
        return "image"
    if ext in DOCUMENT_EXTENSIONS:
        return "document"
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in ARCHIVE_EXTENSIONS or mime_type in (
        "application/zip",
        "application/x-zip-compressed",
        "application/x-tar",
        "application/gzip",
        "application/x-7z-compressed",
        "application/x-rar-compressed",
    ):
        return "archive"
    return "unknown"


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def extract_text_from_pdf(raw: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text
    except ImportError:
        return "[pdfminer not installed — cannot extract PDF text]"

    try:
        return extract_text(io.BytesIO(raw)) or ""
    except Exception as exc:
        logger.warning(f"PDF extraction failed: {exc}")
        return ""


def extract_text_from_docx(raw: bytes) -> str:
    try:
        import docx
    except ImportError:
        return "[python-docx not installed — cannot extract DOCX text]"

    try:
        document = docx.Document(io.BytesIO(raw))
        return "".join(p.text for p in document.paragraphs)
    except Exception as exc:
        logger.warning(f"DOCX extraction failed: {exc}")
        return ""


def extract_text_from_plain(raw: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def extract_document_text(filename: str, raw: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        return extract_text_from_pdf(raw)
    if ext == ".docx":
        return extract_text_from_docx(raw)
    return extract_text_from_plain(raw)


# ---------------------------------------------------------------------------
# ZIP / Archive Processing
# ---------------------------------------------------------------------------

@dataclass
class ExtractedFile:
    filename: str
    relative_path: str
    size: int
    raw: bytes
    file_type: str
    mime_type: str


def extract_zip_contents(raw: bytes) -> List[ExtractedFile]:
    """Extract all files from a ZIP archive, detect their types, and return structured data."""
    extracted = []
    total_size = 0

    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue

                # Skip macOS metadata files and hidden files
                if info.filename.startswith("__MACOSX/") or os.path.basename(info.filename).startswith("."):
                    continue

                # Check limits
                if len(extracted) >= config.MAX_ARCHIVE_FILES:
                    logger.warning(f"Archive exceeds max file limit ({config.MAX_ARCHIVE_FILES}), skipping remaining files")
                    break

                try:
                    file_raw = zf.read(info.filename)
                    total_size += len(file_raw)

                    if total_size > config.MAX_ARCHIVE_TOTAL_SIZE:
                        logger.warning(f"Archive exceeds max total size ({config.MAX_ARCHIVE_TOTAL_SIZE} bytes), stopping extraction")
                        break

                    mime = mimetypes.guess_type(info.filename)[0] or "application/octet-stream"
                    ftype = detect_file_type(info.filename, mime)

                    extracted.append(ExtractedFile(
                        filename=os.path.basename(info.filename),
                        relative_path=info.filename,
                        size=len(file_raw),
                        raw=file_raw,
                        file_type=ftype,
                        mime_type=mime,
                    ))
                except Exception as exc:
                    logger.warning(f"Failed to extract {info.filename}: {exc}")

    except zipfile.BadZipFile:
        logger.error("Invalid ZIP file format")
        raise HTTPException(status_code=400, detail="Invalid ZIP file format")
    except Exception as exc:
        logger.error(f"ZIP extraction error: {exc}")
        raise HTTPException(status_code=500, detail=f"ZIP extraction failed: {exc}")

    return extracted


def analyze_archive_file(file_info: ExtractedFile) -> Dict[str, Any]:
    """Analyze a single file extracted from an archive."""
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
            img_result = run_image_pipeline(file_info.filename, file_info.raw, file_info.mime_type)
            result["analysis"] = {
                "summary": img_result.get("summary", ""),
                "description": img_result.get("description", ""),
                "objects": img_result.get("objects", []),
                "text": img_result.get("text", ""),
            }
        elif file_info.file_type == "document":
            doc_result = run_document_pipeline(file_info.filename, file_info.raw)
            result["analysis"] = {
                "summary": doc_result.get("summary", ""),
                "key_points": doc_result.get("key_points", []),
                "text_preview": doc_result.get("text", "")[:500],
            }
        elif file_info.file_type == "code":
            code_result = run_code_pipeline(file_info.filename, file_info.raw)
            result["analysis"] = {
                "summary": code_result.get("summary", ""),
                "key_points": code_result.get("key_points", []),
                "language": code_result.get("description", ""),
            }
        else:
            text = extract_text_from_plain(file_info.raw)
            result["analysis"] = {
                "summary": "Unknown file type — raw text extraction attempted." if text.strip() else "Binary or unreadable file.",
                "text_preview": text[:500] if text.strip() else "",
            }
    except Exception as exc:
        logger.warning(f"Analysis failed for {file_info.filename}: {exc}")
        result["analysis"] = {"error": str(exc), "summary": "Analysis failed for this file."}

    return result


# ---------------------------------------------------------------------------
# AI Pipelines
# ---------------------------------------------------------------------------

def run_image_pipeline(filename: str, raw: bytes, mime_type: str) -> Dict[str, Any]:
    if config.MOCK_AI:
        return {
            "summary": "[MOCK] Image analyzed — placeholder scene description.",
            "description": "[MOCK] This is a placeholder description of the image contents.",
            "key_points": [],
            "objects": ["[mock-object-1]", "[mock-object-2]"],
            "text": "[MOCK] OCR text would appear here if detected.",
            "insights": ["[MOCK] This appears to be a UI screenshot."],
            "image_details": {
                "scene_description": "[MOCK] A placeholder scene showing generic objects.",
                "objects_detected": ["[mock] person", "[mock] building", "[mock] vehicle"],
                "text_ocr": "[MOCK] Sample OCR text: 'Welcome to the app'",
                "ui_interpretation": "[MOCK] This appears to be a login screen with username and password fields.",
                "colors_dominant": ["#3B82F6", "#1F2937", "#F3F4F6"],
                "composition": "[MOCK] Centered layout with header at top, form in middle, footer at bottom.",
                "mood_atmosphere": "[MOCK] Professional, clean, modern corporate aesthetic.",
                "technical_quality": "[MOCK] High resolution, good lighting, sharp focus, no visible compression artifacts.",
                "safety_flags": [],
            }
        }

    client = get_gemini_client()

    if config.ENABLE_DETAILED_IMAGE_ANALYSIS:
        prompt = (
            "You are an expert computer vision analyst. Analyze this image in extreme detail. "
            "Provide a comprehensive analysis covering ALL of the following aspects:

"
            "1. SCENE DESCRIPTION: A vivid, detailed paragraph describing what is happening in the image, "
            "including setting, context, and any narrative elements.
"
            "2. OBJECTS DETECTED: A comprehensive list of ALL distinct physical objects, people, animals, "
            "vehicles, buildings, furniture, tools, devices, clothing items, food, plants, etc. Be exhaustive.
"
            "3. TEXT (OCR): ALL visible text in the image — signs, labels, UI text, handwriting, logos, "
            "watermarks, timestamps, captions, URLs, phone numbers, etc. Preserve line breaks.
"
            "4. UI/APP INTERPRETATION: If this is a screenshot or UI image, describe the interface in detail: "
            "what app/website it is, what page/screen, what buttons/fields are present, what the user flow appears to be, "
            "design system used (Material, iOS, etc.), and any visible data/state. If not a UI, say 'Not a UI screenshot.'
"
            "5. DOMINANT COLORS: List the 3-5 most prominent colors as hex codes.
"
            "6. COMPOSITION: Describe the visual layout — rule of thirds, symmetry, focal points, "
            "depth of field, perspective, framing, leading lines, etc.
"
            "7. MOOD & ATMOSPHERE: The emotional tone — cheerful, somber, tense, peaceful, chaotic, "
            "professional, casual, luxurious, minimalist, etc. Explain why.
"
            "8. TECHNICAL QUALITY: Resolution estimate, lighting quality, focus sharpness, "
            "noise/grain, compression artifacts, exposure, color balance, camera angle.
"
            "9. SAFETY FLAGS: Any content that may be sensitive — violence, nudity, hate symbols, "
            "drug paraphernalia, self-harm, etc. List specifically what was detected. Empty array if none.

"
            "Respond ONLY as JSON with this exact structure:
"
            "{
"
            '  "scene_description": "string",
'
            '  "objects_detected": ["string", "string"],
'
            '  "text_ocr": "string",
'
            '  "ui_interpretation": "string",
'
            '  "colors_dominant": ["#RRGGBB"],
'
            '  "composition": "string",
'
            '  "mood_atmosphere": "string",
'
            '  "technical_quality": "string",
'
            '  "safety_flags": ["string"]
'
            "}
"
            "No markdown, no preamble, no explanation outside the JSON."
        )
    else:
        prompt = (
            "Analyze this image. Provide: (1) a concise scene description, "
            "(2) a list of distinct objects detected, (3) any text visible in the "
            "image via OCR, and (4) if this looks like a UI/app screenshot, a short "
            "interpretation of what the interface is doing. "
            "Respond ONLY as JSON with keys: description, objects (array of strings), "
            "text (string), insights (array of strings). No markdown, no preamble."
        )

    from google.genai import types

    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=raw, mime_type=mime_type or "image/jpeg"),
            prompt,
        ],
    )

    parsed = _parse_json_response(response.text)

    if config.ENABLE_DETAILED_IMAGE_ANALYSIS:
        image_details = ImageAnalysisDetail(
            scene_description=parsed.get("scene_description", ""),
            objects_detected=parsed.get("objects_detected", []),
            text_ocr=parsed.get("text_ocr", ""),
            ui_interpretation=parsed.get("ui_interpretation", ""),
            colors_dominant=parsed.get("colors_dominant", []),
            composition=parsed.get("composition", ""),
            mood_atmosphere=parsed.get("mood_atmosphere", ""),
            technical_quality=parsed.get("technical_quality", ""),
            safety_flags=parsed.get("safety_flags", []),
        )

        scene = parsed.get("scene_description", "")
        summary = scene[:280] if scene else "Image analyzed successfully."

        return {
            "summary": summary,
            "description": scene,
            "key_points": [],
            "objects": parsed.get("objects_detected", []),
            "text": parsed.get("text_ocr", ""),
            "insights": [
                f"UI: {parsed.get('ui_interpretation', 'N/A')}",
                f"Mood: {parsed.get('mood_atmosphere', 'N/A')}",
                f"Tech: {parsed.get('technical_quality', 'N/A')}",
            ] if any([parsed.get("ui_interpretation"), parsed.get("mood_atmosphere"), parsed.get("technical_quality")]) else [],
            "image_details": image_details.model_dump(),
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


def run_document_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    extracted_text = extract_document_text(filename, raw)

    if config.MOCK_AI:
        return {
            "summary": "[MOCK] Document summarized — placeholder summary text.",
            "description": "",
            "key_points": ["[mock] Key point one", "[mock] Key point two"],
            "objects": [],
            "text": extracted_text[:2000],
            "insights": ["[MOCK] This document appears to discuss placeholder topics."],
        }

    client = get_gemini_client()
    prompt = (
        "You will be given the extracted text of a document. Provide: "
        "(1) a concise summary, (2) a list of key points, (3) any notable insights. "
        "Respond ONLY as JSON with keys: summary, key_points (array of strings), "
        "insights (array of strings). No markdown, no preamble.

"
        f"DOCUMENT TEXT:
{extracted_text[:config.MAX_TEXT_LENGTH]}"
    )

    response = client.models.generate_content(model=config.GEMINI_MODEL, contents=[prompt])
    parsed = _parse_json_response(response.text)

    return {
        "summary": parsed.get("summary", ""),
        "description": "",
        "key_points": parsed.get("key_points", []),
        "objects": [],
        "text": extracted_text[:2000],
        "insights": parsed.get("insights", []),
    }


def run_code_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    code_text = extract_text_from_plain(raw)
    ext = os.path.splitext(filename.lower())[1].lstrip(".")

    if config.MOCK_AI:
        return {
            "summary": f"[MOCK] {ext} code reviewed — placeholder summary.",
            "description": f"[MOCK] Detected language: {ext}",
            "key_points": ["[mock] No real bugs found (mock mode)"],
            "objects": [],
            "text": code_text[:2000],
            "insights": ["[MOCK] Consider adding more comments (placeholder insight)."],
        }

    client = get_gemini_client()

    if config.ENABLE_SECURITY_SCAN:
        prompt = (
            f"You will be given source code (detected extension: .{ext}). Provide: "
            "(1) a concise summary of what the code does, (2) a list of bugs found, "
            "(3) a list of security issues found, (4) a list of suggested improvements. "
            "Respond ONLY as JSON with keys: summary, bugs (array of strings), "
            "security_issues (array of strings), improvements (array of strings). "
            "No markdown, no preamble.

"
            f"CODE:
{code_text[:config.MAX_TEXT_LENGTH]}"
        )
    else:
        prompt = (
            f"You will be given source code (detected extension: .{ext}). Provide: "
            "(1) a concise summary of what the code does, (2) a list of bugs found, "
            "(3) a list of suggested improvements. "
            "Respond ONLY as JSON with keys: summary, bugs (array of strings), "
            "improvements (array of strings). No markdown, no preamble.

"
            f"CODE:
{code_text[:config.MAX_TEXT_LENGTH]}"
        )

    response = client.models.generate_content(model=config.GEMINI_MODEL, contents=[prompt])
    parsed = _parse_json_response(response.text)

    key_points = [f"[bug] {b}" for b in parsed.get("bugs", [])]
    if config.ENABLE_SECURITY_SCAN:
        key_points += [f"[security] {s}" for s in parsed.get("security_issues", [])]

    return {
        "summary": parsed.get("summary", ""),
        "description": f"Detected language: {ext}",
        "key_points": key_points,
        "objects": [],
        "text": code_text[:2000],
        "insights": parsed.get("improvements", []),
    }


def run_archive_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    """Process a ZIP archive: extract all files, analyze each one, return aggregated results."""
    if not config.ENABLE_ARCHIVE_PROCESSING:
        return {
            "summary": "Archive processing is disabled in config.",
            "description": "",
            "key_points": ["Archive processing disabled."],
            "objects": [],
            "text": "",
            "insights": ["Set ENABLE_ARCHIVE_PROCESSING = True in config.py to enable ZIP analysis."],
            "archive_contents": [],
            "archive_summary": "",
        }

    logger.info(f"Processing ZIP archive: {filename}")

    extracted_files = extract_zip_contents(raw)
    total_files = len(extracted_files)

    if total_files == 0:
        return {
            "summary": "Empty ZIP archive — no files found to analyze.",
            "description": "",
            "key_points": ["Archive contains no extractable files."],
            "objects": [],
            "text": "",
            "insights": ["The uploaded ZIP file appears to be empty or contains only system files."],
            "archive_contents": [],
            "archive_summary": "Empty archive",
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
                "analysis": {
                    "summary": f"[MOCK] {file_info.file_type} file analysis placeholder.",
                    "status": "mock_mode",
                }
            })
        else:
            archive_analyses.append(analyze_archive_file(file_info))

    summary_parts = [f"Archive contains {total_files} files:"]
    for ftype, count in file_type_counts.items():
        if count > 0:
            summary_parts.append(f"  - {count} {ftype} file(s)")

    archive_summary = "
".join(summary_parts)

    if not config.MOCK_AI and total_files > 0:
        try:
            client = get_gemini_client()
            archive_overview = []
            for item in archive_analyses[:20]:
                archive_overview.append(
                    f"File: {item['filename']} ({item['file_type']})
"
                    f"Summary: {item['analysis'].get('summary', 'N/A')[:200]}"
                )

            prompt = (
                "You are analyzing a ZIP archive containing multiple files. "
                "Based on the following file summaries, provide an overall assessment:

"
                "1. What is the likely purpose of this archive?
"
                "2. Are there any patterns or relationships between the files?
"
                "3. Any security concerns or red flags?
"
                "4. Suggested next steps for the user.

"
                "Respond ONLY as JSON with keys: purpose, patterns, security_concerns, next_steps. "
                "No markdown, no preamble.

"
                f"ARCHIVE CONTENTS:
{'
---
'.join(archive_overview)}"
            )

            response = client.models.generate_content(model=config.GEMINI_MODEL, contents=[prompt])
            parsed = _parse_json_response(response.text)

            ai_summary = (
                f"Purpose: {parsed.get('purpose', 'Unknown')} | "
                f"Patterns: {parsed.get('patterns', 'None detected')} | "
                f"Security: {parsed.get('security_concerns', 'None')}"
            )
            archive_summary += f"

AI Assessment:
{ai_summary}"

        except Exception as exc:
            logger.warning(f"Archive AI summary failed: {exc}")

    return {
        "summary": f"Archive analyzed: {total_files} files extracted and processed.",
        "description": "",
        "key_points": [
            f"Total files: {total_files}",
            f"Images: {file_type_counts['image']}",
            f"Documents: {file_type_counts['document']}",
            f"Code files: {file_type_counts['code']}",
            f"Other/Unknown: {file_type_counts['unknown']}",
        ],
        "objects": [],
        "text": "",
        "insights": [archive_summary],
        "archive_contents": archive_analyses,
        "archive_summary": archive_summary,
    }


def run_unknown_pipeline(filename: str, raw: bytes) -> Dict[str, Any]:
    extracted_text = extract_text_from_plain(raw)
    has_readable_text = bool(extracted_text.strip())

    return {
        "summary": (
            "Unrecognized file type — best-effort raw text extraction attempted."
            if has_readable_text
            else "Unrecognized file type and no readable text could be extracted."
        ),
        "description": "",
        "key_points": [],
        "objects": [],
        "text": extracted_text[:2000] if has_readable_text else "",
        "insights": [
            "This file type is not explicitly supported. "
            "Results may be incomplete or inaccurate."
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> Dict[str, Any]:
    """Gemini sometimes wraps JSON in markdown fences — strip those before parsing."""
    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse model JSON output: {exc}")
        return {"summary": text[:500]}


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    raw = await file.read()
    size = len(raw)

    if size > config.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {config.MAX_FILE_SIZE / (1024*1024):.1f} MB"
        )

    mime_type = file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    file_type = detect_file_type(file.filename, mime_type)

    logger.info(f"Analyzing '{file.filename}' ({size} bytes, {mime_type}) -> detected as '{file_type}'")

    try:
        if file_type == "image":
            result = run_image_pipeline(file.filename, raw, mime_type)
        elif file_type == "document":
            result = run_document_pipeline(file.filename, raw)
        elif file_type == "code":
            result = run_code_pipeline(file.filename, raw)
        elif file_type == "archive":
            result = run_archive_pipeline(file.filename, raw)
        else:
            result = run_unknown_pipeline(file.filename, raw)
    except RuntimeError as exc:
        logger.error(f"Pipeline configuration error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during analysis")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    response = AnalyzeResponse(
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
        ),
    )

    return JSONResponse(content=response.model_dump())
