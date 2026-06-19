# 🔷 IGRIS FILE INTELLIGENCE API

> **"Drop any file. Get full intelligence."**

A production-grade FastAPI backend that ingests **any file type** — images, documents, code, or entire ZIP archives — and returns structured, AI-powered analysis via a single endpoint.

---

## ⚡ What It Does

| You Upload | IGRIS Returns |
|-----------|---------------|
| 🖼️ Image (jpg, png, webp) | Scene description, object detection, OCR text, UI breakdown, dominant colors, composition, mood, technical quality, safety flags |
| 📄 Document (pdf, docx, txt, md) | Full text extraction, AI summary, key points, insights |
| 💻 Code (js, py, html, etc.) | Language detection, bug scan, security vulnerability audit, improvement suggestions |
| 🗜️ ZIP Archive | Recursive extraction + individual analysis of every file inside + archive-wide AI assessment |
| ❓ Unknown | Best-effort raw text extraction |

**One endpoint. Every file type. Structured JSON out.**

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   File Upload   │────▶│  Type Detection  │────▶│  AI Pipeline    │
│   (any format)  │     │ (ext + MIME)     │     │ (Gemini 2.5)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
                                              ┌─────────────────────┐
                                              │  Structured JSON      │
                                              │  {summary, analysis, │
                                              │   meta, insights}    │
                                              └─────────────────────┘
```

---

## 🚀 Quick Start

### 1. Configure

```bash
nano config.py
```

```python
# config.py
GEMINI_API_KEY = "AIzaSy..."          # ← Your Google AI Studio key
MOCK_AI = ""                           # Auto: mock if no key, live if key present
GEMINI_MODEL = "gemini-2.5-flash"     # or "gemini-2.5-pro" for deeper analysis
```

### 2. Deploy

```bash
# Local dev (auto-reload)
./deploy.sh local

# OR production Docker
./deploy.sh prod
```

### 3. Test

```bash
curl http://localhost:8000/health

curl -X POST -F "file=@screenshot.png" http://localhost:8000/analyze
```

---

## 📡 API Endpoints

### `GET /`
Service status and configuration overview.

**Response:**
```json
{
  "service": "IGRIS AI Backend",
  "version": "2.0.0",
  "status": "online",
  "mock_mode": false,
  "model": "gemini-2.5-flash",
  "features": ["image_analysis", "document_analysis", "code_analysis", "zip_processing"],
  "endpoint": "POST /analyze"
}
```

---

### `GET /health`
Lightweight health check for load balancers and monitoring.

**Response:**
```json
{
  "status": "ok",
  "mock_mode": false,
  "model": "gemini-2.5-flash"
}
```

---

### `POST /analyze` ⭐
The core endpoint. Accepts any file upload and returns structured intelligence.

**Request:**
```bash
curl -X POST \
  -F "file=@your_file.png" \
  http://localhost:8000/analyze
```

**Response Schema:**
```json
{
  "file_type": "image | document | code | archive | unknown",
  "summary": "One-line AI summary of the file",
  "analysis": {
    "description": "Detailed description or scene narrative",
    "key_points": ["Bullet-point insights"],
    "objects": ["Detected objects (images only)"],
    "text": "Extracted or OCR'd text",
    "insights": ["AI-generated observations and recommendations"],
    "image_details": {
      "scene_description": "Vivid scene narrative",
      "objects_detected": ["person", "laptop", "coffee cup"],
      "text_ocr": "All visible text from image",
      "ui_interpretation": "Detailed UI/app breakdown if screenshot",
      "colors_dominant": ["#1E293B", "#3B82F6", "#F8FAFC"],
      "composition": "Visual layout analysis",
      "mood_atmosphere": "Emotional tone with reasoning",
      "technical_quality": "Resolution, lighting, focus assessment",
      "safety_flags": []
    },
    "archive_contents": [
      {
        "filename": "app.py",
        "relative_path": "src/app.py",
        "size": 2048,
        "file_type": "code",
        "mime_type": "text/x-python",
        "analysis": { "summary": "...", "key_points": [...] }
      }
    ],
    "archive_summary": "Archive contains 12 files: 5 code, 3 images, 4 documents..."
  },
  "meta": {
    "filename": "your_file.png",
    "size": 245760,
    "mime_type": "image/png",
    "extracted_files": 0
  }
}
```

---

## 🧠 Pipeline Deep-Dive

### 🖼️ Image Pipeline
Triggered by: `.jpg` `.jpeg` `.png` `.webp` `.gif` `.bmp` `.tiff` `.ico`

**AI Prompt asks for:**
1. Scene description (narrative)
2. All objects detected (exhaustive list)
3. OCR text (signs, labels, UI text, handwriting)
4. UI interpretation (app name, page, buttons, user flow, design system)
5. Dominant colors (hex codes)
6. Composition (rule of thirds, symmetry, focal points)
7. Mood & atmosphere (emotional tone)
8. Technical quality (resolution, lighting, focus, noise)
9. Safety flags (violence, nudity, hate symbols, etc.)

**Toggle:** `ENABLE_DETAILED_IMAGE_ANALYSIS = True/False` in `config.py`

---

### 📄 Document Pipeline
Triggered by: `.pdf` `.docx` `.txt` `.md` `.rtf` `.doc` `.odt`

**Flow:**
1. Extract text (pdfminer for PDFs, python-docx for DOCX, raw decode for text)
2. Send to Gemini with structured prompt
3. Returns: summary, key points, insights

**Text truncation:** Respects `MAX_TEXT_LENGTH` config (default 30,000 chars)

---

### 💻 Code Pipeline
Triggered by: 80+ extensions including `.py` `.js` `.ts` `.html` `.css` `.java` `.go` `.rs` `.php` `.sql` `.vue` `.svelte` `.sol` `.tf` and more.

**AI Prompt asks for:**
- Summary of what the code does
- Bug list
- Security vulnerabilities (if `ENABLE_SECURITY_SCAN = True`)
- Suggested improvements

**Returns structured as:**
```json
{
  "key_points": [
    "[bug] Variable 'x' is used before assignment",
    "[security] SQL injection risk in line 42",
    "[security] Hardcoded API key detected"
  ],
  "insights": [
    "Consider using parameterized queries",
    "Add input validation for user data"
  ]
}
```

---

### 🗜️ Archive Pipeline
Triggered by: `.zip` `.tar` `.gz` `.tgz` `.bz2` `.xz` `.7z` `.rar`

**Flow:**
1. Extract all files (skips `__MACOSX/` and hidden files)
2. Detect type of each extracted file
3. Route each to its own pipeline (image/document/code/unknown)
4. Aggregate results + AI-generated archive assessment

**Safety limits:**
- Max files per archive: `MAX_ARCHIVE_FILES` (default 100)
- Max total extracted size: `MAX_ARCHIVE_TOTAL_SIZE` (default 200 MB)

**Toggle:** `ENABLE_ARCHIVE_PROCESSING = True/False`

---

## ⚙️ Configuration (`config.py`)

```python
# ===== AI Settings =====
GEMINI_API_KEY = ""                    # Your API key
MOCK_AI = ""                           # ""=auto, "true"=mock, "false"=live
GEMINI_MODEL = "gemini-2.5-flash"      # Model selection

# ===== Server =====
HOST = "0.0.0.0"
PORT = 8000
RELOAD = True                          # Dev only
WORKERS = 1                            # Set to 4+ in production

# ===== Limits =====
MAX_FILE_SIZE = 50 * 1024 * 1024       # 50 MB upload cap
MAX_ARCHIVE_FILES = 100
MAX_ARCHIVE_TOTAL_SIZE = 200 * 1024 * 1024
MAX_TEXT_LENGTH = 30000                # Token safety for Gemini

# ===== Feature Toggles =====
ENABLE_DETAILED_IMAGE_ANALYSIS = True
ENABLE_ARCHIVE_PROCESSING = True
ENABLE_SECURITY_SCAN = True

# ===== CORS =====
CORS_ORIGINS = ["*"]                   # Restrict in production!
```

**Env vars override file values** — useful for deployment secrets:
```bash
export GEMINI_API_KEY="your_key"
export MOCK_AI="false"
```

---

## 🐳 Docker Deployment

```bash
# Build & start
./deploy.sh prod

# Or manual Docker
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

**Production container features:**
- Non-root user (`igris`) for security
- Gunicorn + Uvicorn workers (4 workers, ASGI)
- Health checks every 30s
- Resource limits: 2 CPU / 2GB RAM
- Log rotation: 10MB max, 3 files
- Auto-restart on crash

---

## 📋 Response Schemas

### `AnalyzeResponse`
| Field | Type | Description |
|-------|------|-------------|
| `file_type` | `string` | `image` `document` `code` `archive` `unknown` |
| `summary` | `string` | One-line AI summary |
| `analysis` | `AnalysisBlock` | Detailed structured analysis |
| `meta` | `MetaBlock` | File metadata |

### `AnalysisBlock`
| Field | Type | Description |
|-------|------|-------------|
| `description` | `string` | Scene narrative or file overview |
| `key_points` | `string[]` | Bullet insights |
| `objects` | `string[]` | Detected objects (images) |
| `text` | `string` | Extracted/OCR text |
| `insights` | `string[]` | AI observations & recommendations |
| `image_details` | `ImageAnalysisDetail?` | Deep image analysis (images only) |
| `archive_contents` | `object[]` | Per-file analyses (archives only) |
| `archive_summary` | `string` | Archive overview (archives only) |

### `ImageAnalysisDetail`
| Field | Type | Description |
|-------|------|-------------|
| `scene_description` | `string` | Vivid narrative of image contents |
| `objects_detected` | `string[]` | All physical objects identified |
| `text_ocr` | `string` | All visible text |
| `ui_interpretation` | `string` | UI/app breakdown if screenshot |
| `colors_dominant` | `string[]` | Hex color codes |
| `composition` | `string` | Visual layout analysis |
| `mood_atmosphere` | `string` | Emotional tone |
| `technical_quality` | `string` | Resolution, lighting, focus, noise |
| `safety_flags` | `string[]` | Sensitive content warnings |

### `MetaBlock`
| Field | Type | Description |
|-------|------|-------------|
| `filename` | `string` | Original filename |
| `size` | `integer` | File size in bytes |
| `mime_type` | `string` | Detected MIME type |
| `extracted_files` | `integer` | Count of files inside archive (0 for non-archives) |

---

## 🔒 Security

- **File size limits** enforced before processing
- **Archive extraction caps** prevent zip bombs
- **Non-root container user**
- **CORS configurable** per environment
- **Safety flags** in image analysis for content moderation
- **Code security scanning** detects vulnerabilities automatically

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI + Pydantic v2 |
| Server | Uvicorn (dev) / Gunicorn + Uvicorn Workers (prod) |
| AI Engine | Google Gemini 2.5 Flash / Pro |
| Container | Docker + Docker Compose |
| Document Parsing | pdfminer.six, python-docx |
| Language | Python 3.12 |

---

## 📄 License

MIT — use it, break it, improve it.

---

> **IGRIS** — *Intelligence Gathering & Recognition Information System*
>
> Built for files. Powered by Gemini. Structured for machines.
