# OSINT Multimodal Verification Engine

An autonomous, serverless-ready multimodal AI engine and verification pipeline for real-time claim investigation, rumor tracking, image OCR context validation, and stance classification.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [License](#license)

---

## Overview

The **OSINT Multimodal Verification Engine** is an automated claim verification system built to ingest text claims, article URLs, and media images across multiple languages. It scours web data sources, performs vector semantic similarity search, evaluates stance using local zero-shot machine learning models, dynamically scores source credibility, and generates human-readable explanations using local or cloud LLMs.

The platform consists of:
1. **FastAPI Backend (`backend/`)**: Provides REST endpoints (`/verify`, `/v1/verify`, `/v1/status/{job_id}`, `/v1/history`, `/v1/metrics`, `/health`) and WebSockets (`/ws/{job_id}`) for asynchronous task orchestration via Celery & Redis.
2. **React Dashboard (`frontend/`)**: Interactive Web UI featuring real-time progress indicators, stance visualization, source credibility metrics, and claim mutation chain analysis.
3. **Chrome Extension (`extension/`)**: Manifest V3 extension enabling right-click claim context-menu verification, image OCR scanning, and live side-panel results on any web page.
4. **Data Infrastructure (`infra/`)**: PostgreSQL container initialized with `pgvector` and `pgcrypto` extensions for vector search over 384-dimensional sentence embeddings (`all-MiniLM-L6-v2`) and automated claim mutation tracking.

---

## Features

- 🌍 **Multilingual Ingestion & Translation**: Detects input text language (`langdetect`) and normalizes claims via `deep-translator` before querying OSINT search interfaces.
- 📸 **Multimodal Image Processing**: Extracts embedded image text using `EasyOCR` and `Pillows`, executing context-mismatch and reverse-image evidence analysis.
- ⚖️ **Zero-Shot Stance Classification**: Evaluates web evidence using PyTorch and `facebook/bart-large-mnli` stance classification (`SUPPORTING`, `CONTRADICTING`, `NEUTRAL`).
- 🎯 **Deterministic Verdict Computation**: Computes mathematically grounded verdicts (`TRUE`, `FALSE`, `MISLEADING`, `CONFLICTING`, `UNVERIFIED`) based on multi-domain stance aggregation and credibility tiers.
- 🧠 **Local & Cloud LLM Synthesis**: Generates 4-sentence factual summaries using local LM Studio inference servers (e.g. DeepSeek-R1, Qwen-VL) with optional fallback to Google Gemini (`google-genai`).
- ⚡ **Asynchronous Task Queue & Streaming**: Runs jobs using Celery workers with Redis broker/backend and streams real-time stage execution over WebSocket channels.
- 🔍 **Vector Search & Mutation Tracking**: Generates claim vector embeddings and indexes them using pgvector `ivfflat` cosine similarity to detect rumor mutations across time.
- 🌐 **Chrome Browser Extension**: Context-menu bindings to verify highlighted text, images, article links, or active web pages directly in Chrome.

---

## Architecture

```mermaid
graph TD
    subgraph Clients
        FE["React Dashboard (frontend/)"]
        EXT["Chrome Extension Manifest V3 (extension/)"]
    end

    subgraph API & Queue
        API["FastAPI Backend (backend/main.py)"]
        REDIS["Redis 7 (Cache / Broker / WS PubSub)"]
        CELERY["Celery Worker (backend/tasks.py)"]
    end

    subgraph Intelligence & Scraping
        NLP["BART-MNLI / MiniLM Embedder"]
        OCR["EasyOCR / Pillow"]
        LLM["LM Studio / Google Gemini API"]
        SCRAPER["OSINT Scrapers (DDG, GDELT, NewsAPI, Wiki, Reddit)"]
    end

    subgraph Persistence
        PG[("PostgreSQL 16 + pgvector (osint_postgres)")]
    end

    FE -->|HTTP / REST| API
    FE -->|WebSocket Stage Stream| API
    EXT -->|REST / WS| API

    API -->|Read/Write Cache & WS Events| REDIS
    API -->|Enqueue Jobs| REDIS
    REDIS -->|Task Execution| CELERY

    CELERY -->|Claim Scraping| SCRAPER
    CELERY -->|Stance & Vector Embeddings| NLP
    CELERY -->|Image Text Extraction| OCR
    CELERY -->|Explanation Synthesis| LLM

    CELERY -->|Persist Claims, Reports & Mutations| PG
    API -->|Fetch History & Metrics| PG
```

---

## Tech Stack

### Backend
- **Language**: Python 3.10+
- **Framework**: FastAPI `^0.111.0`, Uvicorn `^0.30.0`, Pydantic `^2.0.0`, Pydantic Settings `^2.0.0`
- **Asynchronous Task Processing**: Celery `^5.3.0`, Redis `^5.0.0`, asyncpg `^0.29.0`
- **Machine Learning & NLP**: PyTorch `^2.2.0`, Transformers `^4.40.0` (`facebook/bart-large-mnli`), Sentence-Transformers `^2.7.0` (`all-MiniLM-L6-v2`), spaCy `^3.7.0`
- **Vision & Translation**: EasyOCR `^1.7.0`, Pillow `^10.0.0`, `langdetect` `^1.0.9`, `deep-translator` `^1.11.0`
- **LLM Clients**: OpenAI SDK `^1.30.0` (for LM Studio), `google-genai` `^1.0.0`

### Frontend & Extension
- **Frontend Framework**: React `^18.2.0`, React DOM `^18.2.0`, `react-scripts` `5.0.1`
- **UI Animation**: Framer Motion `^12.38.0`
- **Chrome Extension**: Manifest V3, Vanilla JavaScript, CSS HTML

### Infrastructure & Database
- **Database**: PostgreSQL 16 (`pgvector/pgvector:pg16`) with `vector` and `pgcrypto` extensions
- **Cache & Message Broker**: Redis 7 Alpine (`redis:7-alpine`)
- **Containerization**: Docker Compose (`docker-compose.yml`)

---

## Prerequisites

- **Docker & Docker Compose**: Docker Desktop or Docker Engine with `compose` plugin.
- **Python**: Version 3.10 or higher.
- **Node.js & npm**: Node.js 18+ and npm installed.
- **LM Studio (Optional for local LLM inference)**: Set up on `http://localhost:1234/v1` with a vision or text model loaded.
- **Google Chrome**: Version 102+ (for loading unpacked Manifest V3 extension).

---

## Installation

### 1. Repository Setup

Clone the repository:

```bash
git clone https://github.com/Omiiii04/Hackathon.git
cd Hackathon
```

### 2. Environment Configuration

Copy the environment template file:

```bash
cp .env.example .env
```

*Note: Update credentials or API keys inside `.env` if using optional cloud providers (e.g. Gemini, NewsAPI, SERP API).*

### 3. Infrastructure Containers

Start PostgreSQL (pgvector) and Redis using Docker Compose:

```bash
docker compose up -d
```

Verify that both containers (`osint_postgres` and `osint_redis`) are healthy:

```bash
docker compose ps
```

### 4. Backend Setup

Navigate to the `backend/` directory, create a virtual environment, and install dependencies:

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell:
.\venv\Scripts\Activate
# Activate on Linux/macOS:
# source venv/bin/activate

# Install required Python packages
pip install -r ../requirements.txt
```

### 5. Frontend Setup

Navigate to the `frontend/` directory and install dependencies:

```bash
cd ../frontend
npm install
```

---

## Configuration

All configuration variables are defined in `.env` and validated via `backend/config.py` using `pydantic-settings`.

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `POSTGRES_DB` | Yes | PostgreSQL database name | `osint_verify` |
| `POSTGRES_USER` | Yes | PostgreSQL user | `omii` |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password | `omii00` |
| `POSTGRES_HOST` | No | PostgreSQL host | `localhost` |
| `POSTGRES_PORT` | No | PostgreSQL port | `5432` |
| `DATABASE_URL` | Yes | Asyncpg connection URL | `postgresql://omii:omii00@localhost:5432/osint_verify` |
| `REDIS_URL` | Yes | Redis connection string | `redis://localhost:6379/0` |
| `LM_STUDIO_BASE_URL` | No | LM Studio API endpoint | `http://localhost:1234/v1` |
| `LM_STUDIO_MODEL` | No | LM Studio model identifier | `local-model` |
| `LM_STUDIO_TIMEOUT` | No | LM Studio request timeout (seconds) | `60` |
| `GEMINI_API_KEY` | No | Google Gemini API key | `""` |
| `GEMINI_MODEL` | No | Gemini model name | `gemini-3-flash-preview` |
| `WIKIPEDIA_EMAIL` | No | Email sent in User-Agent header to Wikipedia API | `omapar0123@gmail.com` |
| `NEWS_API_KEY` | No | NewsAPI.org API key | `""` |
| `GOOGLE_FACTCHECK_API_KEY` | No | Google Fact Check API key | `""` |
| `SERP_API_KEY` | No | SERP API key | `""` |
| `GDELT_ENABLED` | No | Enable GDELT global news scraping | `true` |
| `DDG_ENABLED` | No | Enable DuckDuckGo HTML scraper | `true` |
| `REDDIT_ENABLED` | No | Enable Reddit public JSON API scraper | `true` |
| `EVIDENCE_MAX_ARTICLES` | No | Max web articles gathered per claim | `5` |
| `EVIDENCE_MAX_SENTENCES` | No | Max candidate sentences processed | `5` |
| `EARLY_EXIT_TIER1_THRESHOLD` | No | Tier-1 domain count for early pipeline exit | `2` |
| `EARLY_EXIT_RATIO_HIGH` | No | High threshold ratio for early verdict exit | `0.80` |
| `EARLY_EXIT_RATIO_LOW` | No | Low threshold ratio for early verdict exit | `0.20` |
| `MUTATION_SIMILARITY_THRESHOLD` | No | Cosine similarity threshold for claim mutation tracking | `0.75` |
| `CONFIDENCE_SIGMOID_SCALE` | No | Sigmoid scale multiplier for confidence score | `10` |
| `CIRCUIT_BREAKER_FAIL_MAX` | No | Max consecutive failures before tripping circuit breaker | `3` |
| `CIRCUIT_BREAKER_RESET_SECONDS` | No | Circuit breaker reset timeout (seconds) | `60` |
| `HTTP_REQUEST_TIMEOUT_SECONDS` | No | HTTP client timeout per request (seconds) | `8` |
| `GATHER_TIMEOUT_SECONDS` | No | Aggregated scraping timeout (seconds) | `20` |
| `FREEZE_CREDIBILITY` | No | Freeze dynamic credibility updates | `false` |
| `SECRET_KEY` | No | Application secret key | `change-me-generate-with-python-secrets` |
| `OFFLINE_MODE` | No | Disable external network scraping | `false` |
| `CACHE_TTL_DAYS` | No | Verification result cache TTL (days) | `7` |

---

## Usage

### 1. Running the FastAPI Server

From the `backend/` directory with your virtual environment activated:

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The server initializes PostgreSQL, Redis connection pools, BART-MNLI weights, and MiniLM embedding models upon startup.

### 2. Running Celery Worker (Optional Asynchronous Task Processing)

In a separate terminal (from `backend/` directory):

On Windows:
```bash
celery -A tasks.celery_app worker --loglevel=info --pool=solo
```

On Linux / macOS:
```bash
celery -A tasks.celery_app worker --loglevel=info
```

### 3. Running the React Web Interface

From the `frontend/` directory:

```bash
npm start
```

Access the React dashboard at `http://localhost:3000`.

### 4. Loading the Chrome Extension

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer Mode** using the top-right toggle switch.
3. Click **Load unpacked**.
4. Select the `extension/` directory from this repository.
5. Highlight any text or right-click any image on any webpage and select **Verify Claim** or **Scan & Verify Image**.

---

## Project Structure

```text
├── .env.example              # Environment configuration template
├── docker-compose.yml        # Docker service definitions (PostgreSQL + Redis)
├── requirements.txt          # Python dependency manifest
├── test_db.py                # Database connection check script
├── backend/                  # FastAPI application & ML pipeline
│   ├── main.py               # Application entry point, CORS middleware & REST/WS routes
│   ├── config.py             # Single source of truth settings (Pydantic BaseSettings)
│   ├── tasks.py              # Celery asynchronous task worker definition
│   ├── scraper.py            # Multithreaded OSINT web scraper
│   ├── models.py             # Data schemas (EvidenceItem, ClaimVerificationResult)
│   ├── verdict_engine.py     # Stance aggregation and verdict determination rules
│   ├── image_engine.py       # Image OCR text extraction and image verification logic
│   ├── explainer.py          # LLM explanation synthesis orchestrator
│   ├── db/                   # Database pool, tables initialization & asyncpg queries
│   ├── pipeline/             # Modular ML components (stance, embedder, temporal, diversity)
│   ├── services/             # Circuit breaker and LLM inference service wrapper
│   └── ws/                   # WebSocket connection manager
├── frontend/                 # React UI Dashboard
│   ├── package.json          # React application dependencies and scripts
│   ├── public/               # Static assets & HTML template
│   └── src/                  # React components (App.js, VerdictCard, MutationChains, etc.)
├── extension/                # Chrome Extension (Manifest V3)
│   ├── manifest.json         # Extension permissions, service worker & content script declarations
│   ├── background/           # Service worker (background.js) handling context menus & API requests
│   ├── content/              # Injected side panel logic (content.js, content.css)
│   └── popup/                # Extension popup UI (popup.html, popup.js, popup.css)
├── infra/                    # Database setup scripts
│   └── init.sql              # Idempotent PostgreSQL schema init script (pgvector, tables, seed data)
└── tests/                    # Automated test suite
    ├── conftest.py           # pytest configuration & PYTHONPATH setup
    ├── test_performance_controls.py # Performance and timeout test suite
    └── test_verdict_v2.py    # Stance, diversity, temporal & verdict test suite
```

---

## Testing

Backend test cases are implemented using `pytest`.

### Executing Backend Tests

Ensure test dependencies (`pytest`) are installed in your Python environment:

```bash
pytest tests/
```

Individual test suites:
```bash
# Run verdict calculation and pipeline tests
pytest tests/test_verdict_v2.py

# Run performance and timeout control tests
pytest tests/test_performance_controls.py
```

### Database Verification Script

To verify TCP connectivity and schema initialization against Docker PostgreSQL:

```bash
python test_db.py
```

---

## Deployment

Local development and service orchestration are configured using Docker Compose.

### Docker Containers

The deployment includes:
- **`osint_postgres`**: Image `pgvector/pgvector:pg16`. Exposes port `5432:5432`. Mounts `infra/init.sql` to automatically apply extensions (`vector`, `pgcrypto`), indexes, and baseline credibility table seeds on initial boot.
- **`osint_redis`**: Image `redis:7-alpine`. Exposes port `6379:6379`. Configured with LRU memory eviction (`maxmemory 512mb`).

Command reference:
```bash
# Start background services
docker compose up -d

# View container logs
docker compose logs -f

# Stop services
docker compose down

# Stop services and remove persistent data volumes
docker compose down -v
```

<!-- NEEDS INPUT: Production containerization Dockerfile for backend FastAPI app and production build deployment configs (e.g. Kubernetes/Helm) not present in repository. -->

---

## Contributing

1. Fork the repository and create your feature branch: `git checkout -b feature/my-feature`.
2. Maintain code standards and run existing tests before submitting a pull request.
3. Ensure no hardcoded secrets or API keys are committed. Use `.env.example` to document any new environment variables.

---

## Troubleshooting

### PostgreSQL Connection Errors
- Ensure Docker container `osint_postgres` is running (`docker compose ps`).
- Check that port `5432` is not occupied by a local PostgreSQL installation.
- Verify `DATABASE_URL` in `.env` matches credentials in `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.

### Missing ML Model Weights / First Run Delays
- On first startup, `facebook/bart-large-mnli` and `sentence-transformers/all-MiniLM-L6-v2` weights will download automatically from HuggingFace. Ensure an active internet connection during initial boot.

### Celery Worker Execution on Windows
- Celery requires `--pool=solo` on Windows systems. Ensure you pass `--pool=solo` when running `celery -A tasks.celery_app worker` on Windows.

---

## License

<!-- NEEDS INPUT: LICENSE file is missing in the repository. Please add a LICENSE file to define open-source terms. -->
