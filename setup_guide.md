# Setup Guide — OSINT Rumor Verification Platform

**Version:** 5.2.0 | **Team:** Radio Frequency | **Event:** VIT Code Apex 2.0

This guide walks through every step to get the platform running — from zero to a working demo — including the local LM Studio LLM runtime (no API keys needed), all services, the Chrome extension, and the React dashboard.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Repository Setup](#2-repository-setup)
3. [Environment Configuration](#3-environment-configuration)
4. [LM Studio Local LLM Setup](#4-lm-studio-local-llm-setup)
5. [Docker Services Startup](#5-docker-services-startup)
6. [Database Initialisation](#6-database-initialisation)
7. [Model Downloads](#7-model-downloads)
8. [Backend Startup (without Docker)](#8-backend-startup-without-docker)
9. [Celery Worker Startup](#9-celery-worker-startup)
10. [Frontend Dashboard Setup](#10-frontend-dashboard-setup)
11. [Chrome Extension Installation](#11-chrome-extension-installation)
12. [Standalone Verdict Pipeline](#12-standalone-verdict-pipeline)
13. [Pre-loading Demo Claims](#13-pre-loading-demo-claims)
14. [Verify Everything Works](#14-verify-everything-works)
15. [Offline / No-Internet Mode](#15-offline--no-internet-mode)
16. [Troubleshooting](#16-troubleshooting)
17. [Demo Day Checklist](#17-demo-day-checklist)

---

## 1. Prerequisites

### 1.1 Required Software

| Software                | Version | Install                            |
| ----------------------- | ------- | ---------------------------------- |
| Python                  | 3.11+   | https://python.org                 |
| Node.js                 | 18+     | https://nodejs.org                 |
| Docker + Docker Compose | Latest  | https://docs.docker.com/get-docker |
| Git                     | Any     | https://git-scm.com                |
| LM Studio               | Latest  | https://lmstudio.ai                |
| Chrome                  | v100+   | For extension dev/test             |

### 1.2 Hardware Requirements

| Resource | Minimum         | Recommended          |
| -------- | --------------- | -------------------- |
| RAM      | 8 GB            | 16 GB                |
| GPU VRAM | None (CPU mode) | 6 GB (RTX 4050/3060) |
| Disk     | 15 GB free      | 25 GB free           |
| CPU      | 4 cores         | 8 cores              |

> **No GPU?** The system runs fully on CPU. BART-MNLI just takes ~3× longer per call. Expect cold-start verdicts in ~20–25s instead of ~8–10s.

### 1.3 API Keys (All Optional — System Works Without Them)

| Key                      | Source                           | Required?                             |
| ------------------------ | -------------------------------- | ------------------------------------- |
| GEMINI_API_KEY           | https://aistudio.google.com      | ❌ Optional (fallback #1)             |
| XAI_API_KEY              | https://console.x.ai             | ❌ Optional (Grok fallback)           |
| SERP_API_KEY             | https://serpapi.com              | ❌ Optional                           |
| NEWS_API_KEY             | https://newsapi.org              | ❌ Optional                           |
| GOOGLE_FACTCHECK_API_KEY | https://console.cloud.google.com | ❌ Optional                           |
| GOOGLE_VISION_API_KEY    | https://console.cloud.google.com | ❌ Optional (image verification only) |

> **For demo with no keys:** Keep `LM Studio` running locally and leave the cloud keys blank. If venue internet is unreliable, set `OFFLINE_MODE=true` and rely on LM Studio + pre-cached claims.

---

## 2. Repository Setup

```bash
# Clone the repository
git clone https://github.com/your-team/osint-verify.git
cd osint-verify

# Confirm structure
ls
# Expected:
# backend/  extension/  frontend/  verdict_pipeline/
# docker-compose.yml  Dockerfile  requirements.txt  .env.example
```

---

## 3. Environment Configuration

```bash
# Copy the example env file
cp .env.example .env
```

Open `.env` in any editor and fill in your values:

```env
# ── LOCAL LLM (PRIMARY — no key needed) ─────────────────────────────
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen3-4b-2507
OFFLINE_MODE=false

# ── CLOUD LLM FALLBACKS (optional) ──────────────────────────────────
GEMINI_API_KEY=           # leave blank if not using
XAI_API_KEY=              # leave blank if not using Grok

# ── DATA SOURCES ─────────────────────────────────────────────────────
SERP_API_KEY=             # leave blank if not using
NEWS_API_KEY=             # at minimum, get this free key from newsapi.org
GOOGLE_FACTCHECK_API_KEY= # leave blank if not using
GOOGLE_VISION_API_KEY=    # leave blank if not using image verification

# ── INFRASTRUCTURE ───────────────────────────────────────────────────
DATABASE_URL=postgresql://omii:omii00@localhost:5432/hackathon_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=generate_a_random_32_character_string_here
DB_PASSWORD=omii00

# ── ALGORITHM ────────────────────────────────────────────────────────
EVIDENCE_MAX_ARTICLES=5
EVIDENCE_MAX_SENTENCES=5
EARLY_EXIT_TIER1_THRESHOLD=2
EARLY_EXIT_RATIO_HIGH=0.80
EARLY_EXIT_RATIO_LOW=0.20
CIRCUIT_BREAKER_FAIL_MAX=3
CIRCUIT_BREAKER_RESET_SECONDS=60
CONFIDENCE_SIGMOID_SCALE=10
MUTATION_SIMILARITY_THRESHOLD=0.75
ADVERSARIAL_PARAPHRASE_THRESHOLD=0.70

# ── UX ───────────────────────────────────────────────────────────────
UX_BUFFER_MS=1800
```

> **Generate SECRET_KEY:**
>
> ```bash
> python -c "import secrets; print(secrets.token_hex(16))"
> ```

---

**Recommended LLM stack**

- LM Studio primary model: `qwen3-4b-2507`
- LM Studio local backup model: `llama-3.2-3b`
- Gemini fallback model: `gemini-3-flash-preview`
- Grok fallback model: `grok-4.20-reasoning`

## 4. LM Studio Local LLM Setup

LM Studio runs the LLM locally and exposes an OpenAI-compatible API at `http://localhost:1234/v1`. That keeps the explanation step local while still working with the same OpenAI client code shape.

### 4.1 Install LM Studio

```bash
# Download and install LM Studio from:
# https://lmstudio.ai
```

### 4.2 Download the Models

```bash
# In LM Studio -> Discover / Search, download these:
# 1. qwen/qwen3-4b-2507      ← primary local explanation model
# 2. llama-3.2-3b            ← optional local backup if you want a smaller fallback
#
# If LM Studio shows multiple quantisations, choose a 4-bit GGUF variant
# (for example Q4_K_M) for the best speed / memory balance on a 6 GB GPU.
```

**Why these two local models?**

- `qwen3-4b-2507` is the primary recommendation for this project: strong instruction following, small enough for LM Studio on a typical Windows laptop/desktop, and better aligned with short grounded explanation generation than older 8B CPU-first setups.
- `llama-3.2-3b` is the lightweight backup: slightly smaller and still fast enough for the 120-token explanation cap.

### 4.3 Start the LM Studio Server

```bash
# In LM Studio:
# 1. Open the Developer / Local Server tab
# 2. Select qwen3-4b-2507
# 3. Click Start Server
#
# Verify the API is running:
curl http://localhost:1234/v1/models
# Expected: JSON listing qwen3-4b-2507
```

> **Tip:** If your backend runs inside WSL 2, use `http://host.docker.internal:1234/v1` instead of `http://localhost:1234/v1`.

### 4.4 Test LM Studio via Python

```bash
python -c "
from openai import OpenAI
client = OpenAI(base_url='http://localhost:1234/v1', api_key='lm-studio')
r = client.chat.completions.create(
    model='qwen3-4b-2507',
    messages=[{'role':'user','content':'Reply with just: WORKING'}],
    temperature=0.0,
    max_tokens=10              # hard cap always applied
)
print(r.choices[0].message.content)
"
# Expected: WORKING
```

---

## 5. Docker Services Startup

This starts PostgreSQL and Redis in Docker. LM Studio stays outside Docker as a desktop app / local server.

### 5.1 Start Core Services

```bash
# From project root
docker compose up -d postgres redis

# Verify both are running
docker compose ps
# Expected: postgres Running, redis Running
```

### 5.2 Local LLM Runtime

```bash
# Keep LM Studio open and confirm the local server is still up
curl http://localhost:1234/v1/models
```

### 5.3 Verify Services

```bash
# PostgreSQL
docker exec hackathon pg_isready -U omii
# Expected: accepting connections

# Redis
docker exec hackathon redis-cli ping
# Expected: PONG

# LM Studio local server
curl http://localhost:1234/v1/models
# Expected: JSON with qwen3-4b-2507
```

---

## 6. Database Initialisation

### 6.1 Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
# OR: venv\Scripts\activate     # Windows

# Install all dependencies
pip install -r requirements.txt

# Verify key packages
python -c "import fastapi, celery, asyncpg, pgvector; print('OK')"
```

### 6.2 Run Database Migrations

```bash
cd backend

# Create tables and extensions
python -c "
import asyncio
from db.database import create_all_tables
asyncio.run(create_all_tables())
print('Tables created.')
"

# OR if using Alembic migrations:
alembic upgrade head
```

### 6.3 Seed Source Credibility Data

```bash
python -c "
import asyncio
from db.database import seed_credibility_data
asyncio.run(seed_credibility_data())
print('Credibility data seeded.')
"
```

### 6.4 Verify Database

```bash
docker exec hackathon psql -U omii -d hackathon_db -c "\dt"
# Expected: List of tables including claims, reports, sources,
#           mutation_chains, source_credibility_dynamic, telemetry_nli, etc.
```

---

## 7. Model Downloads

These are the NLP models used by the pipeline. Download once — they are cached locally.

### 7.1 spaCy Language Model

```bash
python -m spacy download en_core_web_sm
# ~12 MB download

# Verify
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('spaCy OK')"
```

### 7.2 Sentence Transformers (MiniLM)

```bash
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
print('MiniLM downloaded and cached.')
"
# ~80 MB download, cached in ~/.cache/huggingface/
```

### 7.3 BART-large-MNLI (Stance Classifier)

```bash
python -c "
from transformers import pipeline
import torch
device = 0 if torch.cuda.is_available() else -1
clf = pipeline('zero-shot-classification',
               model='facebook/bart-large-mnli', device=device)
result = clf('The earth is round.', candidate_labels=['true', 'false'])
print('BART-MNLI OK:', result['labels'][0])
"
# ~1.6 GB download, cached in ~/.cache/huggingface/
# This is the slowest download — expect 5-10 minutes
```

### 7.4 (Optional) EasyOCR for Image Verification

```bash
python -c "
import easyocr
reader = easyocr.Reader(['en'])
print('EasyOCR OK')
"
# ~100 MB download
```

> **Summary of disk usage after downloads:**
>
> ```
> spaCy en_core_web_sm      ~12 MB
> MiniLM all-MiniLM-L6-v2   ~80 MB
> BART-large-MNLI           ~1.6 GB
> LM Studio qwen3-4b-2507   ~2.3-2.5 GB   <- primary local model
> LM Studio llama-3.2-3b    ~2.0 GB       <- optional local backup
> EasyOCR (optional)        ~100 MB
> -------------------------------------------------
> Total                     ~4.3-4.5 GB (with both LM Studio models)
> ```
>
> Previously listed Ollama / Llama 3.1 8B downloads are no longer the recommended path.

---

## 8. Backend Startup (without Docker)

### 8.1 Start FastAPI Server

```bash
cd backend

# Development mode with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Expected output:
# INFO:     Application startup complete.
# INFO:     GPU VRAM allocated: 1.60GB / 6.00GB   (if GPU present)
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 8.2 Verify Backend

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "ok", "models_loaded": true}

# Metrics
curl http://localhost:8000/v1/metrics
# Expected: JSON with verdict_distribution, cache_hit_rate, etc.
```

### 8.3 Quick Verification Test

```bash
curl -X POST http://localhost:8000/v1/verify \
  -H "Content-Type: application/json" \
  -d '{"claim": "COVID vaccines contain microchips", "input_type": "text"}'

# Expected:
# {"job_id": "...", "status": "queued", "websocket_url": "ws://..."}
```

---

## 9. Celery Worker Startup

The Celery worker processes verification jobs from the Redis queue.

### 9.1 Start Worker

```bash
# In a NEW terminal, from project root
source venv/bin/activate
cd backend

celery -A tasks worker \
  --loglevel=info \
  --concurrency=4 \
  --pool=prefork

# Expected output:
# [tasks.verify_claim_task] -> osint_verify
# celery@hostname ready.
```

### 9.2 (Optional) Celery Flower — Task Monitor

```bash
# In another terminal
pip install flower
celery -A backend.tasks flower --port=5555

# Open http://localhost:5555 to see task queue, workers, and results
```

---

## 10. Frontend Dashboard Setup

### 10.1 Install Dependencies

```bash
cd frontend
npm install
```

### 10.2 Configure API URL

```bash
# Create frontend env file
echo "VITE_API_URL=http://localhost:8000/v1" > .env.local
echo "VITE_WS_URL=ws://localhost:8000" >> .env.local
```

### 10.3 Start Development Server

```bash
npm run dev

# Expected:
#   VITE ready in XXms
#   Local:   http://localhost:5173/
```

Open http://localhost:5173 in Chrome.

### 10.4 Build for Production

```bash
npm run build
# Output: frontend/dist/

# Serve production build
npm run preview
```

---

## 11. Chrome Extension Installation

### 11.1 Update API URL in Extension

```bash
# Edit extension/background.js
# Change the API_BASE constant:
# const API_BASE = "http://localhost:8000/v1";
```

```bash
# On Linux/Mac — quick sed replacement:
sed -i 's|https://api.osint-verify.io/v1|http://localhost:8000/v1|g' \
  extension/background.js
```

### 11.2 Load Extension in Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle top-right)
3. Click **"Load unpacked"**
4. Select the `extension/` folder from the project root
5. Confirm the extension appears with the OSINT Verify icon

### 11.3 Test the Extension

1. Open any news article in Chrome
2. Select any text (e.g. a headline)
3. Right-click → **"Verify Claim"**
4. The popup should open and show the WebSocket progress stream
5. Within 8–10 seconds (cold start), the Killer Screen result should appear

### 11.4 Reload After Changes

```bash
# After editing any extension file:
# 1. Go to chrome://extensions/
# 2. Click the reload icon (↺) on the OSINT Verify card
# OR press Ctrl+Shift+I in the popup → reload
```

---

## 12. Standalone Verdict Pipeline

The standalone module works without FastAPI, Celery, or Redis — useful for batch analysis and research.

### 12.1 Install (Minimal Dependencies)

```bash
pip install sentence-transformers transformers torch spacy
python -m spacy download en_core_web_sm
```

### 12.2 Use as Python Import

```python
from verdict_pipeline import run_verdict_text

result = run_verdict_text(
    claim_text="COVID vaccines contain microchips",
    evidence_dicts=[]   # provide pre-collected evidence, or leave empty
)

print(result.verdict)     # FALSE
print(result.confidence)  # 0.xx
print(result.trace)       # full algorithm trace
```

### 12.3 Use as CLI

```bash
# Single claim
python -m verdict_pipeline verify "Iran lost the war"

# With pre-collected evidence file
python -m verdict_pipeline verify "Iran lost the war" \
  --evidence evidence.json

# Batch mode — one claim per line
python -m verdict_pipeline batch claims.txt

# Batch with JSONL output
python -m verdict_pipeline batch claims.txt --output results.jsonl
```

### 12.4 Example `claims.txt`

```
COVID vaccines contain microchips
NASA confirmed alien life on Mars
The moon landing was faked
```

---

## 13. Pre-loading Demo Claims

Pre-cache the 5 benchmark claims before demo day. This ensures instant results via Redis even if something goes wrong with live API calls.

### 13.1 Run the Pre-cache Script

```bash
cd backend

python -c "
import asyncio
from cache.redis_client import redis
from pipeline import run_pipeline_with_early_exit
from claim_parser import parse_claim
import hashlib, json

BENCHMARK_CLAIMS = [
    'Iran lost the war',
    'NASA confirmed alien life',
    'COVID vaccines contain microchips',
    'Artemis mission launched in 2022',
    'New virus outbreak started in India',
]

async def precache():
    for claim in BENCHMARK_CLAIMS:
        key = f'claim:{hashlib.md5(claim.encode()).hexdigest()}'
        existing = await redis.get(key)
        if existing:
            print(f'Already cached: {claim[:40]}')
            continue
        print(f'Running pipeline for: {claim[:40]}...')
        parsed = parse_claim(claim)
        result = await run_pipeline_with_early_exit(parsed, 'precache')
        await redis.setex(key, 86400 * 7, result.json())   # 7-day TTL for demo
        print(f'  Cached: {result.verdict} ({result.confidence})')

asyncio.run(precache())
print('All benchmark claims pre-cached.')
"
```

### 13.2 Verify Cache

```bash
python -c "
import asyncio
import redis.asyncio as aioredis
import hashlib

async def check():
    r = aioredis.from_url('redis://localhost:6379/0')
    claims = [
        'Iran lost the war',
        'NASA confirmed alien life',
        'COVID vaccines contain microchips',
        'Artemis mission launched in 2022',
        'New virus outbreak started in India',
    ]
    for c in claims:
        key = f'claim:{hashlib.md5(c.encode()).hexdigest()}'
        val = await r.get(key)
        status = '✅ CACHED' if val else '❌ MISSING'
        print(f'{status}: {c}')

asyncio.run(check())
"
```

---

## 14. Verify Everything Works

Run this end-to-end test to confirm the entire stack:

### 14.1 Full Pipeline Test

```bash
python -c "
import asyncio, httpx, json

async def test():
    async with httpx.AsyncClient() as client:

        # 1. Submit a claim
        r = await client.post('http://localhost:8000/v1/verify',
            json={'claim': 'COVID vaccines contain microchips', 'input_type': 'text'})
        data = r.json()
        print('Job ID:', data['job_id'])
        print('Status:', data['status'])

        # 2. Poll for result (simplified — in real usage, use WebSocket)
        import time
        for i in range(30):
            await asyncio.sleep(1)
            r2 = await client.get(f'http://localhost:8000/v1/status/{data[\"job_id\"]}')
            s2 = r2.json()
            if s2.get('status') == 'complete':
                print()
                print('Verdict:           ', s2['verdict'])
                print('Confidence:        ', s2['confidence'])
                print('Verdict Reason Tag:', s2.get('verdict_reason_tag'))
                print('Top Insight:       ', s2.get('top_insight'))
                print('LLM Provider Used: ', s2.get('algorithm_trace', {}).get('llm_provider_used'))
                print('Support Bar:       ', s2.get('support_bar'))
                break
            print(f'  [{i+1}s] {s2.get(\"stage\", \"waiting\")}...', end='\r')
        else:
            print('Timed out waiting for result.')

asyncio.run(test())
"
```

### 14.2 Expected Output

```
Job ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Status: queued
  [1s] parsing...
  [3s] searching...
  [6s] scoring...
  [8s] explaining...

Verdict:            FALSE
Confidence:         0.87
Verdict Reason Tag: Widely debunked by credible sources
Top Insight:        3 Tier-1 sources (Reuters, BBC, AP) contradict this claim.
LLM Provider Used:  lm_studio
Support Bar:        {'support_pct': 8, 'contradict_pct': 92}
```

### 14.3 Component Checklist

```bash
# All checks in one script
python -c "
checks = []

# 1. LM Studio
try:
    from openai import OpenAI
    c = OpenAI(base_url='http://localhost:1234/v1', api_key='lm-studio')
    r = c.chat.completions.create(model='qwen3-4b-2507',
        messages=[{'role':'user','content':'Reply OK'}], temperature=0.0)
    checks.append(('LM Studio LLM', '✅', r.choices[0].message.content.strip()))
except Exception as e:
    checks.append(('LM Studio LLM', '❌', str(e)))

# 2. spaCy
try:
    import spacy; spacy.load('en_core_web_sm')
    checks.append(('spaCy model', '✅', 'en_core_web_sm loaded'))
except Exception as e:
    checks.append(('spaCy model', '❌', str(e)))

# 3. MiniLM
try:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    emb = m.encode('test')
    checks.append(('MiniLM', '✅', f'dim={len(emb)}'))
except Exception as e:
    checks.append(('MiniLM', '❌', str(e)))

# 4. BART-MNLI
try:
    from transformers import pipeline
    clf = pipeline('zero-shot-classification', model='facebook/bart-large-mnli', device=-1)
    r = clf('test', candidate_labels=['true','false'])
    checks.append(('BART-MNLI', '✅', r['labels'][0]))
except Exception as e:
    checks.append(('BART-MNLI', '❌', str(e)))

# 5. Redis
try:
    import redis; r = redis.from_url('redis://localhost:6379/0'); r.ping()
    checks.append(('Redis', '✅', 'PONG'))
except Exception as e:
    checks.append(('Redis', '❌', str(e)))

# 6. PostgreSQL
try:
    import asyncio, asyncpg
    async def pg():
        conn = await asyncpg.connect('postgresql://osint:yourpassword@localhost:5432/osint_verify')
        v = await conn.fetchval('SELECT version()')
        await conn.close()
        return v[:30]
    v = asyncio.run(pg())
    checks.append(('PostgreSQL', '✅', v))
except Exception as e:
    checks.append(('PostgreSQL', '❌', str(e)))

print()
print('=== SYSTEM CHECK ===')
for name, status, detail in checks:
    print(f'  {status}  {name:<20}  {detail}')
print()
"
```

---

## 15. Offline / No-Internet Mode

For demo day on unreliable venue WiFi:

```bash
# 1. Set offline mode in .env
echo "OFFLINE_MODE=true" >> .env

# 2. Restart backend
# Ctrl+C the running uvicorn, then:
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

In `OFFLINE_MODE=true`:

- LM Studio handles all LLM calls locally
- Pre-cached benchmark claims return instantly from Redis
- Wikipedia scraper still works (local requests)
- Cloud LLMs (Gemini, Grok) are skipped entirely
- News/Search APIs are skipped — only cached results used

```bash
# Test offline mode
curl -X POST http://localhost:8000/v1/verify \
  -H "Content-Type: application/json" \
  -d '{"claim": "COVID vaccines contain microchips"}'
# Should return instantly from cache (no outbound requests)
```

---

## 16. Troubleshooting

### "LM Studio model not loaded"

```bash
# Open LM Studio and confirm the selected server model is loaded
curl http://localhost:1234/v1/models
```

### "CUDA out of memory"

```bash
# Check current GPU usage
nvidia-smi

# Reduce LM Studio GPU layers in the app until the VRAM meter drops.
# Keep enough headroom for BART-MNLI on the backend GPU.

# Restart BART only (reloads with fresh VRAM)
docker compose restart backend
```

### "asyncio RuntimeError: no running event loop" in Celery

```bash
# This means a Celery task used `await` directly without asyncio.run()
# Every async call in tasks.py MUST be wrapped:
#
# WRONG:  result = await run_pipeline(...)
# RIGHT:  result = asyncio.run(run_pipeline(...))
#
# Check tasks.py for bare awaits.
grep -n "await" backend/tasks.py
```

### "pgvector extension not found"

```bash
# Ensure you're using the pgvector image, not plain postgres
docker compose down
docker compose up -d postgres  # uses pgvector/pgvector:pg16 image

# Then re-run migrations
cd backend && alembic upgrade head
```

### "Circuit breaker always open"

```bash
# Reset all circuit breakers (clears Redis CB keys)
python -c "
import redis
r = redis.from_url('redis://localhost:6379/0')
keys = r.keys('cb:*')
if keys:
    r.delete(*keys)
    print(f'Cleared {len(keys)} circuit breaker keys')
else:
    print('No circuit breaker keys found')
"
```

### Extension shows no results / popup blank

```bash
# 1. Open Chrome DevTools in the popup:
#    Right-click popup → Inspect
# 2. Check Console for errors
# 3. Confirm API_BASE in background.js points to localhost:8000
# 4. Confirm CORS is enabled in FastAPI:
grep -n "CORSMiddleware" backend/main.py
```

### Slow cold-start verdicts (>20s)

```bash
# Check if BART-MNLI is on GPU
python -c "
import torch
from transformers import pipeline
clf = pipeline('zero-shot-classification', model='facebook/bart-large-mnli',
               device=0 if torch.cuda.is_available() else -1)
print('Device:', clf.device)
"
# If device=-1, GPU is not available — CPU mode is slower but works
```

### "Redis connection refused"

```bash
# Start Redis if not running
docker compose up -d redis
# Verify
docker compose ps redis
```

---

## 17. Demo Day Checklist

Run through this list 30 minutes before presenting:

### Services

- [ ] `docker compose ps` — postgres ✅, redis ✅
- [ ] LM Studio: `curl http://localhost:1234/v1/models` → shows `qwen3-4b-2507`
- [ ] `curl http://localhost:8000/health` → `{"status": "ok", "models_loaded": true}`
- [ ] Frontend running at `http://localhost:5173`
- [ ] Celery worker running in a terminal

### Credibility Safety Lock

- [ ] `FREEZE_CREDIBILITY=true` set in `.env` — prevents any feedback from shifting scores during demo
- [ ] Verify: submit a feedback → source scores unchanged

### Cache

- [ ] All 5 benchmark claims pre-cached (run step 13 to refresh TTLs)
- [ ] Redis has data: `docker exec osint-verify-redis-1 redis-cli dbsize`
- [ ] Test one benchmark claim via curl → instant response from cache

### Extension

- [ ] Loaded in Chrome (`chrome://extensions/`)
- [ ] Test right-click on a webpage → popup opens
- [ ] Cached claim shows in <2s with UX buffer
- [ ] UNVERIFIED state tested — shows dashed empty bar (not 0%/0%)

### Offline Prep

- [ ] Disable WiFi → try "COVID vaccines contain microchips" → cached FALSE, LM Studio explains
- [ ] Confirm LLM explanation arrives in <10s (TTFT streaming visible)
- [ ] Test: stop LM Studio → Gemini fallback kicks in (or rule-based if no API key)

### Killer Screen

- [ ] Verdict badge + confidence visible at top ✅
- [ ] Support/Contradict bar shows (not empty unless UNVERIFIED + 0 evidence) ✅
- [ ] Verdict Reason Tag shows (e.g. "Widely debunked by credible sources") ✅
- [ ] Top Insight line shows ✅
- [ ] Mutation alert shows for COVID claim (part of chain) ✅
- [ ] Credibility shift delta shows on NDTV and similar sources ✅
- [ ] "View Evidence Graph" + "View Timeline" buttons work ✅

### Backup Plan

- [ ] 5 benchmark claims cached — never rely on live scraping for the demo
- [ ] Rule-based fallback tested: stop all LLMs → verdict still completes
- [ ] Screenshots of results in slides for total demo failure scenario

---

## Quick Reference — All Start Commands

### Linux / WSL 2

```bash
# Terminal 1 — Docker services
docker compose up -d postgres redis

# Terminal 2 — LM Studio
# Open LM Studio and keep the Local Server running with qwen3-4b-2507 loaded

# Terminal 3 — FastAPI backend
source venv/bin/activate && cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 4 — Celery worker
source venv/bin/activate && cd backend
celery -A tasks worker --loglevel=info --concurrency=4

# Terminal 5 — Frontend dashboard
cd frontend && npm run dev

# Chrome — load extension from: chrome://extensions/ → Load unpacked → ./extension/
```

### Windows + WSL 2 + LM Studio

```
Windows:  Open LM Studio → Load qwen3-4b-2507 → Start Server (port 1234)
WSL 2:    docker compose up -d postgres redis
WSL 2:    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
WSL 2:    celery -A tasks worker --loglevel=info --concurrency=4
Windows:  cd frontend && npm run dev
Windows:  Load Chrome extension from ./extension/
```

---

## 18. Windows Setup — WSL 2 + LM Studio (Recommended)

> **Do NOT use VirtualBox.** VirtualBox has no PCIe passthrough for consumer GPUs on Windows. Your RTX 4050 will be invisible inside VirtualBox, forcing BART-MNLI to CPU and making cold-start ~60s. Use WSL 2 instead.

### 18.1 Install WSL 2

```powershell
# Run in PowerShell as Administrator
wsl --install -d Ubuntu-22.04

# Restart when prompted, then open Ubuntu 22.04 from Start Menu
# Set a username and password
```

```bash
# Inside WSL 2 — verify GPU is visible
nvidia-smi
# Expected: shows RTX 4050, CUDA version, driver version
# If nvidia-smi not found:
#   → Update NVIDIA drivers on Windows host (drivers auto-share to WSL 2)
#   → Download from https://www.nvidia.com/download/index.aspx
```

### 18.2 Install Docker Desktop with WSL 2 Backend

1. Download Docker Desktop from https://www.docker.com/products/docker-desktop
2. During install: select **"Use WSL 2 instead of Hyper-V"**
3. After install → Settings → Resources → WSL Integration → Enable for Ubuntu-22.04
4. Verify from WSL 2:

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
# Expected: NVIDIA GPU visible inside Docker container
```

### 18.3 Install LM Studio (Windows, not WSL)

1. Download from https://lmstudio.ai
2. Install and open LM Studio on Windows
3. Go to **Search** tab → search `qwen3-4b-2507`
4. Download a **4-bit GGUF** variant (for example `Q4_K_M`) for the best speed / VRAM balance
5. Optionally also download `llama-3.2-3b` as a smaller local backup
6. Go to **Local Server** tab → select `qwen3-4b-2507` → click **Start Server**
7. Default port: `1234`

**GPU layer tuning (critical for VRAM budget):**

- Start with a conservative GPU layer count and watch the VRAM meter
- Keep LM Studio below roughly ~1.5 GB VRAM total for the LLM
- This leaves ~1.6 GB for BART-MNLI + 500 MB CUDA overhead on 6 GB VRAM
- Remaining model layers run on CPU RAM

```bash
# Test LM Studio from WSL 2
curl http://host.docker.internal:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen3-4b-2507","messages":[{"role":"user","content":"Reply OK"}],"max_tokens":5}'
# Expected: JSON response with "OK"
```

### 18.4 Configure Backend to Use LM Studio

In your WSL 2 `.env`:

```env
# Use LM Studio as the primary local LLM
LM_STUDIO_BASE_URL=http://host.docker.internal:1234/v1
LM_STUDIO_MODEL=qwen3-4b-2507
```

### 18.5 WSL 2 Port Forwarding

WSL 2 automatically forwards ports to Windows localhost. Your Chrome extension on Windows can reach the WSL 2 FastAPI server at `http://localhost:8000` — no extra config needed.

```bash
# From WSL 2, start everything as normal
docker compose up -d postgres redis
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# From Windows Chrome, extension reaches: http://localhost:8000/v1  ✅
# From Windows Chrome, dashboard reaches: http://localhost:5173     ✅
```

### 18.6 Full WSL 2 Architecture Diagram

```
Windows Host
│
├── LM Studio (Windows GUI app)
│     └── qwen3-4b-2507 — server at :1234
│         partial GPU offload → keep below ~1.5 GB VRAM
│         remaining layers → CPU RAM
│
├── WSL 2 — Ubuntu 22.04
│     ├── uvicorn main:app           → :8000
│     ├── celery worker              (background)
│     ├── nvidia-smi / CUDA          → RTX 4050 native
│     │
│     └── Docker (WSL 2 backend)
│           ├── postgres:5432
│           └── redis:6379
│
└── Chrome on Windows
      └── Extension + Dashboard → http://localhost:8000 (auto-forwarded)
```

---

*Setup Guide v5.2.0 — OSINT Rumor Verification Platform — Radio Frequency — VIT Code Apex 2.0*
