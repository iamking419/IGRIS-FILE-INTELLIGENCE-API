"""
IGRIS AI Backend - Configuration Module
========================================

Centralized config for all settings. Edit this file directly or override
via environment variables (env vars take precedence over file values).

Get your API key at: https://aistudio.google.com/app/apikey
"""

import os

# ---------------------------------------------------------------------------
# GEMINI AI CONFIGURATION - SET THESE BEFORE DEPLOYING
# ---------------------------------------------------------------------------

# Your Google Gemini API key.
# Get one free at: https://aistudio.google.com/app/apikey
# Paste the full key string below - do NOT include quotes if using env vars.
GEMINI_API_KEY = "AQ.Ab8RN6KpYQD0u2sOuQxk5459qWb2LJ45NX7FR0w0ImfvM5Zt2g"

# Set to "true" to force mock mode (no real AI calls, returns placeholder data).
# Set to "false" to force live mode (requires valid GEMINI_API_KEY).
# Leave empty "" to auto-detect: mock mode if no key, live mode if key present.
MOCK_AI = ""

# Gemini model to use.
# Valid options (as of June 2026):
#   "gemini-3-flash-preview"     - Fast, cheap, multimodal (RECOMMENDED)
#   "gemini-3.5-flash"           - Latest GA release, smartest Flash model
#   "gemini-3.1-flash-lite"      - Ultra cheap, slightly lower quality
#   "gemini-3.1-pro-preview"     - Deep reasoning, highest quality
#   "gemini-2.5-flash"           - Older but stable fallback
# INVALID models that will fail:
#   "gemini-1.5-flash"           - SHUTDOWN (fully deprecated by Google)
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

# Max file upload size in bytes (100 MB default)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Max number of files to process inside a ZIP archive
MAX_ARCHIVE_FILES = 100

# Max total size of extracted archive contents in bytes (200 MB default)
MAX_ARCHIVE_TOTAL_SIZE = 200 * 1024 * 1024

# Max text length to send to Gemini per file (to stay within token limits)
MAX_TEXT_LENGTH = 30000

# Max image dimension (width or height) before resizing
MAX_IMAGE_DIMENSION = 4096

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = "INFO"

# Log format string
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

# Allowed origins for CORS. Use ["*"] for dev, restrict in production.
CORS_ORIGINS = ["*"]

# Allow credentials in CORS requests
CORS_ALLOW_CREDENTIALS = True

# Allowed HTTP methods
CORS_ALLOW_METHODS = ["*"]

# Allowed HTTP headers
CORS_ALLOW_HEADERS = ["*"]

# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

# Enable detailed image analysis (scene, colors, composition, mood, etc.)
ENABLE_DETAILED_IMAGE_ANALYSIS = True

# Enable archive (ZIP) recursive processing
ENABLE_ARCHIVE_PROCESSING = True

# Enable code security scanning
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


GEMINI_API_KEY = _resolve("GEMINI_API_KEY", GEMINI_API_KEY)
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

# Final mock mode resolution
if MOCK_AI_RAW.lower() == "true":
    MOCK_AI = True
elif MOCK_AI_RAW.lower() == "false":
    MOCK_AI = False
else:
    # Auto-detect: mock if no key, live if key present
    MOCK_AI = not bool(GEMINI_API_KEY)

# Validate
if not MOCK_AI and not GEMINI_API_KEY:
    raise RuntimeError(
        "MOCK_AI is disabled but GEMINI_API_KEY is not set. "
        "Either set GEMINI_API_KEY in config.py or set MOCK_AI='true'."
    )
