<div align="center">
  <img src="https://img.shields.io/badge/Hackathon-24HR_%E2%9A%A1-blue?style=for-the-badge&logoColor=white" alt="VIT Hackathon" />
  <h1>🌐 OSINT Multimodal Verification Engine</h1>
  <p>An autonomous, serverless, and completely multilingual AI infrastructure built for the <b>24-Hour Hackathon</b>.</p>
</div>

<br/>

## 🚀 The Vision

In an era of rampant social media misinformation, traditional fact-checkers cannot scale to investigate millions of daily claims. The **OSINT Multimodal Verification Engine** is an end-to-end autonomous pipeline designed to ingest text and images in *any language*, scour the internet for highly-credible evidence, algorithmically determine the truth, and use Local Sovereign LLMs to synthesize a fact-checked explanation instantly.

From a beautiful modern React dashboard to a "Right-Click-to-Verify" Chrome Extension, the truth is just one scan away.

---

## ✨ Core Features

* 🌍 **Universal Multilingual Support**
  * Ingests claims in Turkish, Spanish, German, etc.
  * Natively auto-detects the geometry of the language, securely translates it to English to harness global primary OSINT search parameters, and perfectly translates the final verification explanation *back* into the user's local language.
* 📸 **Intelligent Vision Processing**
  * Upload photographs, memes, or screenshots via Drag & Drop.
  * Powered heavily by **Qwen-VL** or **Gemma 3** natively running via Local LM Studio to read text exactly as written or semantically describe the core action of the image, falling back to `EasyOCR` if the LLM servers drop.
* ⚖️ **Deterministic Verdict Engine**
  * No more LLM hallucinations. The engine gathers sources via an intelligent DuckDuckGo OSINT scraper and uses a massive **BART-MNLI Stance Classifier** to mathematically grade whether the internet *Supports*, *Contradicts*, or feels *Neutral* about the claim.
  * Outputs strictly controlled labels: `TRUE`, `FALSE`, `MISLEADING`, `CONFLICTING`, or `UNVERIFIED`.
* 🧠 **Sovereign Local AI Explanations**
  * Routes verified metrics into a locally hosted proxy Model (e.g., DeepSeek-R1) via LM Studio to automatically write 4-sentence, human-readable explanations summarizing the evidence securely without OpenAI API bills.
* 💎 **Premium Glassmorphic UI & Extensions**
  * A gorgeous `React.js` local dashboard featuring floating drag-and-drop zones, Dynamic Neon glowing borders (Emerald for True, Crimson for False), and real-time pulse loading animations.
  * A bundled Chrome Extension allows journalists or users to actively highlight text on X/Twitter and instantly view the system's verified verdicts.

---

## 🛠️ Tech Stack Architecture

| Layer                       | Technology                                                                 | Purpose                                                                 |
|-----------------------------|----------------------------------------------------------------------------|-------------------------------------------------------------------------|
| **Frontend**                | React 18, Framer Motion                                                    | Glassmorphic dashboard with real-time metrics, history, drag-drop.      |
| **Chrome Extension**        | Manifest V3, Content Scripts                                               | Right-click text/image → verify popup.                                  |
| **Backend API**             | FastAPI, Pydantic, Celery+Redis, Uvicorn                                   | Async/sync claim verification (/v1/verify, WS streaming).               |
| **Database**                | Postgres + pgvector (asyncpg), Redis                                       | Embeddings, history, caching, task queue.                               |
| **ML Pipeline**             | Transformers (BART-large-MNLI), SentenceTransformers (MiniLM), Torch        | Stance classification, semantic ranking, pgvector embeddings.           |
| **Vision**                  | EasyOCR, Pillow (LM Studio Qwen-VL/Gemma-3 fallback)                       | Image text extraction/OCR.                                              |
| **LLM**                     | LM Studio (DeepSeek-R1/Gemini fallback via google-genai)                   | Multilingual explanations, no OpenAI costs.                             |
| **OSINT Sources**           | DuckDuckGo scraper, Wikipedia, langdetect + deep-translator                | Evidence collection, auto-translation.                                  |
| **Infra**                   | Docker Compose (Postgres/Redis), .env config                                | One-command local setup.                                                |

---

## ⚙️ Quickstart (Docker + Local Setup)

### Prerequisites
- Python 3.10+, Node.js 20+, Docker, LM Studio (free, local LLMs).
- Git clone: `git clone <repo> && cd Hackathon`

### 1. Start Infra (DB + Cache)
```bash
docker compose up -d  # Postgres + Redis
```

### 2. Boot LM Studio (for Vision/LLM)
1. Download [LM Studio](https://lmstudio.ai/).
2. Load Vision model (Qwen2-VL-2B / Gemma-3-4B) + Reasoning model (DeepSeek-R1-8B).
3. Start Local Inference Server → `http://localhost:1234`.

### 3. Backend API

### 3. Backend API
```bash
cd backend
python -m venv venv && venv\Scripts\activate  # Windows
pip install -r ../requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
API ready at http://localhost:8000/docs (Swagger) / http://localhost:8000/health

### 4. Frontend Dashboard
```bash
cd frontend
npm ci  # Reproducible install
npm start
```
Open http://localhost:3000 → Drag-drop claims or paste text.

### 5. Chrome Extension
1. chrome://extensions/ → Developer Mode ON.
2. "Load unpacked" → select `extension/` folder.
3. Right-click text/image anywhere → "Verify with OSINT Engine".
