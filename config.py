"""
IGRIS AI Backend — Configuration Module (Production Ready)
==========================================================

All sensitive values come from environment variables.
No secrets are hardcoded.
"""

import os

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _env(name: str, default=None, cast=str):
    value = os.getenv(name)

    if value is None or value.strip() == "":
        return default

    value = value.strip()

    if cast == bool:
        return value.lower() in ("true", "1", "yes", "on")

    if cast == int:
        return int(value)

    if cast == list:
        return [x.strip() for x in value.split(",") if x.strip()]

    return value


# ---------------------------------------------------------------------------
# Gemini AI Configuration
# ---------------------------------------------------------------------------

# REQUIRED: Set this in Render / .env
GEMINI_API_KEY: str = _env("GEMINI_API_KEY", "")

# Model selection
GEMINI_MODEL: str = _env("GEMINI_MODEL", "gemini-3-flash-preview")

# Mock mode (true = no API calls)
MOCK_AI: bool = _env("MOCK_AI", False, bool)


# ---------------------------------------------------------------------------
# Server Configuration
# ---------------------------------------------------------------------------

HOST: str = _env("HOST", "0.0.0.0")
PORT: int = _env("PORT", 8000, int)

RELOAD: bool = _env("RELOAD", False, bool)
WORKERS: int = _env("WORKERS", 1, int)


# ---------------------------------------------------------------------------
# File Processing Limits
# ---------------------------------------------------------------------------

MAX_FILE_SIZE: int = _env("MAX_FILE_SIZE", 50 * 1024 * 1024, int)
MAX_ARCHIVE_FILES: int = _env("MAX_ARCHIVE_FILES", 100, int)
MAX_ARCHIVE_TOTAL_SIZE: int = _env("MAX_ARCHIVE_TOTAL_SIZE", 200 * 1024 * 1024, int)
MAX_TEXT_LENGTH: int = _env("MAX_TEXT_LENGTH", 30000, int)
MAX_IMAGE_DIMENSION: int = _env("MAX_IMAGE_DIMENSION", 4096, int)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL: str = _env("LOG_LEVEL", "INFO")
LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ORIGINS: list = _env("CORS_ORIGINS", ["*"], list)
CORS_ALLOW_CREDENTIALS: bool = _env("CORS_ALLOW_CREDENTIALS", True, bool)
CORS_ALLOW_METHODS: list = _env("CORS_ALLOW_METHODS", ["*"], list)
CORS_ALLOW_HEADERS: list = _env("CORS_ALLOW_HEADERS", ["*"], list)


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

ENABLE_DETAILED_IMAGE_ANALYSIS: bool = _env("ENABLE_DETAILED_IMAGE_ANALYSIS", True, bool)
ENABLE_ARCHIVE_PROCESSING: bool = _env("ENABLE_ARCHIVE_PROCESSING", True, bool)
ENABLE_SECURITY_SCAN: bool = _env("ENABLE_SECURITY_SCAN", True, bool)


# ---------------------------------------------------------------------------
# VALIDATION (hard fail fast)
# ---------------------------------------------------------------------------

if not MOCK_AI and not GEMINI_API_KEY:
    raise RuntimeError(
        "❌ Missing GEMINI_API_KEY. "
        "Set it in Render environment variables or enable MOCK_AI=true."
    )
