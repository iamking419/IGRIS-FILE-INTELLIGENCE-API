"""
IGRIS AI Backend - Configuration Module v6.0 (Groq + Gemini Edition)
====================================================================

Multi-API key rotation + async batching + model tiering.
Groq for text/docs/code. Gemini for vision/images.

Get Groq keys: https://console.groq.com/keys
Get Gemini key: https://aistudio.google.com/app/apikey
"""

import os

# ---------------------------------------------------------------------------
# GROQ AI CONFIGURATION - MULTI-KEY ROTATION
# ---------------------------------------------------------------------------

GROQ_API_KEYS = [
    "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",
    "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",
    "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",
    "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",
]

MOCK_AI = ""

# ---------------------------------------------------------------------------
# GEMINI AI CONFIGURATION - VISION ONLY
# ---------------------------------------------------------------------------

# Your Gemini API key for image/vision analysis
GEMINI_API_KEY = "AQ.Ab8RN6KgXIS7rD-PjveFHlgYZeNEpn3oD8_er8FwnG4H8TiWeA"

# Gemini vision model (native multimodal - can see images)
GEMINI_VISION_MODEL = "gemini-3.5-flash"

# ---------------------------------------------------------------------------
# SPEED TIER SYSTEM
# ---------------------------------------------------------------------------

SPEED_TIER = "fastest"

GROQ_MODEL = ""

# ---------------------------------------------------------------------------
# CONCURRENCY & PERFORMANCE
# ---------------------------------------------------------------------------

MAX_CONCURRENT_FILES = 3
AI_TIMEOUT = 30
AGGRESSIVE_RETRY = False

# ---------------------------------------------------------------------------
# Server Configuration
# ---------------------------------------------------------------------------

HOST = "0.0.0.0"
PORT = 8000
RELOAD = True
WORKERS = 1

# ---------------------------------------------------------------------------
# File Processing Limits
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = 100 * 1024 * 1024
MAX_ARCHIVE_FILES = 100
MAX_ARCHIVE_TOTAL_SIZE = 200 * 1024 * 1024
MAX_TEXT_LENGTH = 30000
MAX_IMAGE_DIMENSION = 4096

# ---------------------------------------------------------------------------
# Logging & CORS
# ---------------------------------------------------------------------------

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

CORS_ORIGINS = ["*"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["*"]
CORS_ALLOW_HEADERS = ["*"]

# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

ENABLE_DETAILED_IMAGE_ANALYSIS = True
ENABLE_ARCHIVE_PROCESSING = True
ENABLE_SECURITY_SCAN = True

# ---------------------------------------------------------------------------
# Internal: Resolve config values (env vars override file values)
# ---------------------------------------------------------------------------

def _resolve(name, default, type_func=str):
    env_val = os.getenv(name, "").strip()
    if env_val:
        if type_func == bool:
            return env_val.lower() in ("true", "1", "yes", "on")
        if type_func == int:
            return int(env_val)
        if type_func == list:
            return [x.strip() for x in env_val.split(",") if x.strip()]
        return env_val
    file_val = globals().get(name, default)
    return file_val


MOCK_AI_RAW = _resolve("MOCK_AI", MOCK_AI)
SPEED_TIER = _resolve("SPEED_TIER", SPEED_TIER)
GROQ_MODEL_OVERRIDE = _resolve("GROQ_MODEL", GROQ_MODEL)
HOST = _resolve("HOST", HOST)
PORT = _resolve("PORT", PORT, int)
RELOAD = _resolve("RELOAD", RELOAD, bool)
WORKERS = _resolve("WORKERS", WORKERS, int)
MAX_FILE_SIZE = _resolve("MAX_FILE_SIZE", MAX_FILE_SIZE, int)
MAX_ARCHIVE_FILES = _resolve("MAX_ARCHIVE_FILES", MAX_ARCHIVE_FILES, int)
MAX_ARCHIVE_TOTAL_SIZE = _resolve("MAX_ARCHIVE_TOTAL_SIZE", MAX_ARCHIVE_TOTAL_SIZE, int)
MAX_TEXT_LENGTH = _resolve("MAX_TEXT_LENGTH", MAX_TEXT_LENGTH, int)
MAX_IMAGE_DIMENSION = _resolve("MAX_IMAGE_DIMENSION", MAX_IMAGE_DIMENSION, int)
MAX_CONCURRENT_FILES = _resolve("MAX_CONCURRENT_FILES", MAX_CONCURRENT_FILES, int)
AI_TIMEOUT = _resolve("AI_TIMEOUT", AI_TIMEOUT, int)
AGGRESSIVE_RETRY = _resolve("AGGRESSIVE_RETRY", AGGRESSIVE_RETRY, bool)
LOG_LEVEL = _resolve("LOG_LEVEL", LOG_LEVEL)
LOG_FORMAT = _resolve("LOG_FORMAT", LOG_FORMAT)
CORS_ORIGINS = _resolve("CORS_ORIGINS", CORS_ORIGINS, list)
CORS_ALLOW_CREDENTIALS = _resolve("CORS_ALLOW_CREDENTIALS", CORS_ALLOW_CREDENTIALS, bool)
CORS_ALLOW_METHODS = _resolve("CORS_ALLOW_METHODS", CORS_ALLOW_METHODS, list)
CORS_ALLOW_HEADERS = _resolve("CORS_ALLOW_HEADERS", CORS_ALLOW_HEADERS, list)
ENABLE_DETAILED_IMAGE_ANALYSIS = _resolve("ENABLE_DETAILED_IMAGE_ANALYSIS", ENABLE_DETAILED_IMAGE_ANALYSIS, bool)
ENABLE_ARCHIVE_PROCESSING = _resolve("ENABLE_ARCHIVE_PROCESSING", ENABLE_ARCHIVE_PROCESSING, bool)
ENABLE_SECURITY_SCAN = _resolve("ENABLE_SECURITY_SCAN", ENABLE_SECURITY_SCAN, bool)

# Resolve Gemini config
GEMINI_API_KEY = _resolve("GEMINI_API_KEY", GEMINI_API_KEY)
GEMINI_VISION_MODEL = _resolve("GEMINI_VISION_MODEL", GEMINI_VISION_MODEL)

# ---------------------------------------------------------------------------
# Speed Tier Model Selection - Groq Models
# ---------------------------------------------------------------------------

SPEED_TIER_MAP = {
    "fastest": "meta-llama/llama-4-scout-17b-16e-instruct",
    "fast": "meta-llama/llama-4-scout-17b-16e-instruct",
    "balanced": "llama-3.3-70b-versatile",
    "quality": "qwen/qwen3-32b",
}

if GROQ_MODEL_OVERRIDE:
    GROQ_MODEL = GROQ_MODEL_OVERRIDE
elif SPEED_TIER in SPEED_TIER_MAP:
    GROQ_MODEL = SPEED_TIER_MAP[SPEED_TIER]
else:
    GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ---------------------------------------------------------------------------
# Multi-Key Resolution
# ---------------------------------------------------------------------------

_env_keys_raw = os.getenv("GROQ_API_KEYS", "").strip()
if _env_keys_raw:
    GROQ_API_KEYS = [k.strip() for k in _env_keys_raw.split(",") if k.strip()]

GROQ_API_KEYS = [k for k in GROQ_API_KEYS if k.strip()]

_current_key_index = 0


def get_next_api_key():
    global _current_key_index
    if not GROQ_API_KEYS:
        return None
    key = GROQ_API_KEYS[_current_key_index % len(GROQ_API_KEYS)]
    _current_key_index = (_current_key_index + 1) % len(GROQ_API_KEYS)
    return key


def get_random_api_key():
    import random
    if not GROQ_API_KEYS:
        return None
    return random.choice(GROQ_API_KEYS)


GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""

# Mock mode resolution
if MOCK_AI_RAW.lower() == "true":
    MOCK_AI = True
elif MOCK_AI_RAW.lower() == "false":
    MOCK_AI = False
else:
    MOCK_AI = not bool(GROQ_API_KEYS)

# Validate Groq
if not MOCK_AI and not GROQ_API_KEYS:
    raise RuntimeError(
        "MOCK_AI is disabled but no GROQ_API_KEYS are set. "
        "Either add keys to GROQ_API_KEYS in config.py or set MOCK_AI='true'."
    )

# Validate Gemini (warn only - images will fallback to Groq text-only if no Gemini key)
if not GEMINI_API_KEY and not MOCK_AI:
    import logging
    logging.getLogger("igris").warning(
        "No GEMINI_API_KEY set. Image analysis will fall back to Groq text-only mode."
    )
