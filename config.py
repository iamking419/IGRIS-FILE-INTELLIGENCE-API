"""
IGRIS AI Backend - Configuration Module v4.0 (Speed Optimized)
=============================================================

Multi-API key rotation + async batching + model tiering for maximum speed.

Get your API keys at: https://aistudio.google.com/app/apikey
"""

import os

# ---------------------------------------------------------------------------
# GEMINI AI CONFIGURATION - MULTI-KEY + SPEED TIERING
# ---------------------------------------------------------------------------

# List of Google Gemini API keys for rotation.
# Add 3-4 keys here. If one hits rate limit, IGRIS auto-switches to the next.
# Format: ["key1", "key2", "key3", "key4"]
# Leave empty [] to use env var GEMINI_API_KEYS (comma-separated)
GEMINI_API_KEYS = [
    "AIzaSyCIb8cy2vV0vJUJXCaT-0Wv15txOon1m5w",  # Key 1
    "AQ.Ab8RN6J6-2LPqubmgLGektEXvFZtsdmPrid7hiw9UQIOJsUWdQ",  # Key 2
    "AIzaSyCo11399qyXyN5aT5y4fazlbQEk9mIsAQI",  # Key 3
    "AQ.Ab8RN6KpYQD0u2sOuQxk5459qWb2LJ45NX7FR0w0ImfvM5Zt2g",  # Key 4
]

# Set to "true" to force mock mode (no real AI calls, returns placeholder data).
# Set to "false" to force live mode (requires valid GEMINI_API_KEYS).
# Leave empty "" to auto-detect: mock mode if no keys, live if keys present.
MOCK_AI = ""

# ---------------------------------------------------------------------------
# SPEED TIER SYSTEM - Choose your tradeoff
# ---------------------------------------------------------------------------
#
# TIER 1: "fastest"  - gemini-3-flash-preview (1-2s, good for images/docs)
# TIER 2: "fast"     - gemini-2.5-flash (2-3s, slightly better quality)
# TIER 3: "balanced" - gemini-3.5-flash (3-4s, best quality/speed ratio)
# TIER 4: "quality"  - gemini-3.1-pro-preview (5-10s, max accuracy)
#
# SPEED_TIER auto-selects the model. Override with GEMINI_MODEL if needed.
SPEED_TIER = "fastest"  # Options: "fastest", "fast", "balanced", "quality"

# Override: Set a specific model to bypass tier system
# Leave empty "" to use SPEED_TIER selection
GEMINI_MODEL = ""

# ---------------------------------------------------------------------------
# CONCURRENCY & BATCHING (Speed Multipliers)
# ---------------------------------------------------------------------------

# Number of files to process in parallel (batch uploads)
# Higher = faster but more memory. Render free tier: keep at 3-5
MAX_CONCURRENT_FILES = 5

# Process archive files in parallel too?
PARALLEL_ARCHIVE_PROCESSING = True

# Timeout per AI call (seconds). Lower = faster fail + retry
AI_TIMEOUT = 15

# Retry failed keys immediately or skip to next?
AGGRESSIVE_RETRY = True

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
SPEED_TIER = _resolve("SPEED_TIER", SPEED_TIER)
GEMINI_MODEL_OVERRIDE = _resolve("GEMINI_MODEL", GEMINI_MODEL)
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
PARALLEL_ARCHIVE_PROCESSING = _resolve("PARALLEL_ARCHIVE_PROCESSING", PARALLEL_ARCHIVE_PROCESSING, bool)
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

# ---------------------------------------------------------------------------
# Speed Tier Model Selection
# ---------------------------------------------------------------------------

SPEED_TIER_MAP = {
    "fastest": "gemini-3-flash-preview",
    "fast": "gemini-2.5-flash",
    "balanced": "gemini-3.5-flash",
    "quality": "gemini-3.1-pro-preview",
}

# Override takes precedence, then speed tier, then default
if GEMINI_MODEL_OVERRIDE:
    GEMINI_MODEL = GEMINI_MODEL_OVERRIDE
elif SPEED_TIER in SPEED_TIER_MAP:
    GEMINI_MODEL = SPEED_TIER_MAP[SPEED_TIER]
else:
    GEMINI_MODEL = "gemini-3-flash-preview"

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
    import random
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
