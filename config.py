import os
from typing import Optional

# ---------------------------------------------------------------------------
# Gemini AI Configuration
# ---------------------------------------------------------------------------

# Your Google Gemini API key.
# Get one at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY: str = "AQ.Ab8RN6JVKZHUiomSv_YMocK3NDmGQGHhA1U-A0BB_GPjUqXcHA"

# Set to "true" to force mock mode (no real AI calls, returns placeholder data).
# Set to "false" to force live mode (requires valid GEMINI_API_KEY).
# Leave empty "" to auto-detect: mock mode if no key, live mode if key present.
MOCK_AI: str = ""

# Gemini model to use.
# Recommended: "gemini-2.5-flash" (fast, cheap, multimodal)
# Alternative: "gemini-2.5-pro" (deeper reasoning, higher quality)
GEMINI_MODEL: str = "gemini-3-flash-preview"

# ---------------------------------------------------------------------------
# Server Configuration
# ---------------------------------------------------------------------------

# Host to bind the FastAPI server
HOST: str = "0.0.0.0"

# Port to run on
PORT: int = 8000

# Enable auto-reload on code changes (dev only)
RELOAD: bool = True

# Number of worker processes (set >1 for production, 1 for dev)
WORKERS: int = 1

# ---------------------------------------------------------------------------
# File Processing Limits
# ---------------------------------------------------------------------------

# Max file upload size in bytes (50 MB default)
MAX_FILE_SIZE: int = 50 * 1024 * 1024

# Max number of files to process inside a ZIP archive
MAX_ARCHIVE_FILES: int = 100

# Max total size of extracted archive contents in bytes (200 MB default)
MAX_ARCHIVE_TOTAL_SIZE: int = 200 * 1024 * 1024

# Max text length to send to Gemini per file (to stay within token limits)
MAX_TEXT_LENGTH: int = 30000

# Max image dimension (width or height) before resizing
MAX_IMAGE_DIMENSION: int = 4096

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL: str = "INFO"

# Log format string
LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

# Allowed origins for CORS. Use ["*"] for dev, restrict in production.
CORS_ORIGINS: list = ["*"]

# Allow credentials in CORS requests
CORS_ALLOW_CREDENTIALS: bool = True

# Allowed HTTP methods
CORS_ALLOW_METHODS: list = ["*"]

# Allowed HTTP headers
CORS_ALLOW_HEADERS: list = ["*"]

# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

# Enable detailed image analysis (scene, colors, composition, mood, etc.)
ENABLE_DETAILED_IMAGE_ANALYSIS: bool = True

# Enable archive (ZIP) recursive processing
ENABLE_ARCHIVE_PROCESSING: bool = True

# Enable code security scanning
ENABLE_SECURITY_SCAN: bool = True

# ---------------------------------------------------------------------------
# Internal: Resolve final values (env vars override file values)
# ---------------------------------------------------------------------------

def _resolve(name: str, default, type_func=str):
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


# Resolve all config values
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
