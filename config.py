"""
IGRIS AI Backend - Configuration Module v3.0
============================================

Multi-API key rotation system for maximum uptime and speed.
Keys are rotated automatically when rate limits are hit.

Get your API keys at: https://aistudio.google.com/app/apikey
"""

import os
import random

# ---------------------------------------------------------------------------
# GEMINI AI CONFIGURATION - MULTI-KEY ROTATION SYSTEM
# ---------------------------------------------------------------------------

# List of Google Gemini API keys for rotation.
# Add 3-4 keys here. If one hits rate limit, IGRIS auto-switches to the next.
# Format: ["key1", "key2", "key3", "key4"]
# Leave empty [] to use env var GEMINI_API_KEYS (comma-separated)
GEMINI_API_KEYS = [
    "AIzaSyBh5vODoa8Nh1hhiUzSy3SB7SlGtDyDWzs",  # Key 1
    "AIzaSyCdLDilDCRsEmOZf77fgBQ92O6STI9eSY4",  # Key 2
    "AIzaSyBoA63GoECBNIizRE-1el3XQNZiIqcpW2g",  # Key 3
    "AIzaSyD80E6_Q2D50mTwW_o3OEHVNnDEqwLGYMU",  # Key 4
    "AIzaSyCIb8cy2vV0vJUJXCaT-0Wv15txOon1m5w",  # Key 5
]

# Set to "true" to force mock mode (no real AI calls, returns placeholder data).
# Set to "false" to force live mode (requires valid GEMINI_API_KEYS).
# Leave empty "" to auto-detect: mock mode if no keys, live if keys present.
MOCK_AI = ""

# Gemini model to use.
GEMINI_MODEL = "gemini-3-flash-preview"

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

MAX_FILE_SIZE = 100 * 1024 * 1024       # 100 MB
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
# Internal: Resolve final values (env vars override file values)
# ---------------------------------------------------------------------------

def _resolve(name, default, type_func=str):
    """Resolve a config value: env var > file value > default."""
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


# Resolve env vars
MOCK_AI_RAW = _resolve("MOCK_AI", MOCK_AI)
GEMINI_MODEL = _resolve("GEMINI_MODEL", GEMINI_MODEL)
HOST = _resolve("HOST", HOST)
PORT = _resolve("PORT", PORT, int)
RELOAD = _resolve("RELOAD", RELOAD, bool)
WORKERS = _resolve("WORKERS", WORKERS, int)
MAX_FILE_SIZE = _resolve("MAX_FILE_SIZE", MAX_FILE_SIZE, int)
MAX_ARCHIVE_FILES = _resolve("MAX_ARCHIVE_FILES", MAX_ARCHIVE_FILES, int)
MAX_ARCHIVE_TOTAL_SIZE = _resolve("MAX_ARCHIVE_TOTAL_SIZE", MAX_ARCHIVE_TOTAL_SIZE, int)
MAX_TEXT_LENGTH = _resolve("MAX_TEXT_LENGTH", MAX_TEXT_LENGTH, int)
MAX_IMAGE_DIMENSION = _resolve("MAX_IMAGE_DIMENSION", MAX_IMAGE_DIMENSION, int)
LOG_LEVEL = _resolve("LOG_LEVEL", LOG_LEVEL)
LOG_FORMAT = _resolve("LOG_FORMAT", LOG_FORMAT)
CORS_ORIGINS = _resolve("CORS_ORIGINS", CORS_ORIGINS, list)
CORS_ALLOW_CREDENTIALS = _resolve("CORS_ALLOW_CREDENTIALS", CORS_ALLOW_CREDENTIALS, bool)
CORS_ALLOW_METHODS = _resolve("CORS_ALLOW_METHODS", CORS_ALLOW_METHODS, list)
CORS_ALLOW_HEADERS = _resolve("CORS_ALLOW_HEADERS", CORS_ALLOW_HEADERS, list)
ENABLE_DETAILED_IMAGE_ANALYSIS = _resolve("ENABLE_DETAILED_IMAGE_ANALYSIS", ENABLE_DETAILED_IMAGE_ANALYSIS, bool)
ENABLE_ARCHIVE_PROCESSING = _resolve("ENABLE_ARCHIVE_PROCESSING", ENABLE_ARCHIVE_PROCESSING, bool)
ENABLE_SECURITY_SCAN = _resolve("ENABLE_SECURITY_SCAN", ENABLE_SECURITY_SCAN, bool)

# ---------------------------------------------------------------------------
# Multi-Key Resolution & Rotation Logic
# ---------------------------------------------------------------------------

# Get keys from env var (comma-separated) or file list
_env_keys = _resolve("GEMINI_API_KEYS", "", str)
if _env_keys:
    GEMINI_API_KEYS = [k.strip() for k in _env_keys.split(",") if k.strip()]

# Filter out empty keys
GEMINI_API_KEYS = [k for k in GEMINI_API_KEYS if k.strip()]

# Current active key index (rotates on rate limit)
_current_key_index = 0


def get_next_api_key():
    """Get the next available API key (rotates on failure)."""
    global _current_key_index
    if not GEMINI_API_KEYS:
        return None
    key = GEMINI_API_KEYS[_current_key_index % len(GEMINI_API_KEYS)]
    _current_key_index = (_current_key_index + 1) % len(GEMINI_API_KEYS)
    return key


def get_random_api_key():
    """Get a random API key from the pool (for load distribution)."""
    if not GEMINI_API_KEYS:
        return None
    return random.choice(GEMINI_API_KEYS)


# Backward compatibility: single key access
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

# Final mock mode resolution
if MOCK_AI_RAW.lower() == "true":
    MOCK_AI = True
elif MOCK_AI_RAW.lower() == "false":
    MOCK_AI = False
else:
    MOCK_AI = not bool(GEMINI_API_KEYS)

# Validate
if not MOCK_AI and not GEMINI_API_KEYS:
    raise RuntimeError(
        "MOCK_AI is disabled but no GEMINI_API_KEYS are set. "
        "Either add keys to GEMINI_API_KEYS in config.py or set MOCK_AI='true'."
    )
