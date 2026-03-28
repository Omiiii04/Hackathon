<div align="center">
  <img src="https://img.shields.io/badge/VIT_Hackathon-24HR_%E2%9A%A1-blue?style=for-the-badge&logoColor=white" alt="VIT Hackathon" />
  <h1>🌐 OSINT Multimodal Verification Engine</h1>
  <p>An autonomous, serverless, and completely multilingual AI infrastructure built for the <b>24-Hour Hackathon at VIT, Pune</b>.</p>
</div>

<br/>

## 🚀 The Vision

In an era of rampant social media misinformation, traditional fact-checkers cannot scale to investigate millions of daily claims. The **OSINT Multimodal Verification Engine** is an end-to-end autonomous pipeline designed to ingest text and images in *any language*, scour the internet for highly-credible evidence, algorithmically determine the truth, and use Local Sovereign LLMs to synthesize a fact-checked explanation instantly. 

From a beautiful modern React dashboard to a "Right-Click-to-Verify" Chrome Extension, the truth is just one scan away.

---

## ✨ Core Features

*   🌍 **Universal Multilingual Support**
    *   Ingests claims in Turkish, Spanish, German, etc.
    *   Natively auto-detects the geometry of the language, securely translates it to English to harness global primary OSINT search parameters, and perfectly translates the final verification explanation *back* into the user's local language.
*   📸 **Intelligent Vision Processing**
    *   Upload photographs, memes, or screenshots via Drag & Drop. 
    *   Powered heavily by **Qwen-VL** or **Gemma 3** natively running via Local LM Studio to read text exactly as written or semantically describe the core action of the image, falling back to `EasyOCR` if the LLM servers drop.
*   ⚖️ **Deterministic Verdict Engine**
    *   No more LLM hallucinations. The engine gathers sources via an intelligent DuckDuckGo OSINT scraper and uses a massive **BART-MNLI Stance Classifier** to mathematically grade whether the internet *Supports*, *Contradicts*, or feels *Neutral* about the claim.
    *   Outputs strictly controlled labels: `TRUE`, `FALSE`, `MISLEADING`, `CONFLICTING`, or `UNVERIFIED`.
*   🧠 **Sovereign Local AI Explanations**
    *   Routes verified metrics into a locally hosted proxy Model (e.g., DeepSeek-R1) via LM Studio to automatically write 4-sentence, human-readable explanations summarizing the evidence securely without OpenAI API bills.
*   💎 **Premium Glassmorphic UI & Extensions**
    *   A gorgeous `React.js` local dashboard featuring floating drag-and-drop zones, Dynamic Neon glowing borders (Emerald for True, Crimson for False), and real-time pulse loading animations.
    *   A bundled Chrome Extension allows journalists or users to actively highlight text on X/Twitter and instantly view the system's verified verdicts.

---

## 🛠️ Tech Stack Architecture

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend UI** | React.js, Framer Motion | Provides a dynamic "Glassmorphism" telemetry dashboard. |
| **Browser UI** | Vanilla JS / CSS | Chrome Extension side-panel integration. |
| **Backend API** | Python, FastAPI, Pydantic | Powers strict data schemas and parallel OSINT routing. |
| **Text Verification** | PyTorch, `facebook/bart-large-mnli` | Zero-shot stance classification locally. |
| **Vision Extractor** | LM Studio (Qwen-VL), EasyOCR | Extracts context natively from dragged images. |
| **Synthesizer** | LM Studio (DeepSeek R1 8B) | Writes the final deterministic human explanation. |
| **Language Bridge** | `google-translator`, `langdetect` | End-to-end language agnostic routing. |

---

## ⚙️ How to Run Locally

### 1. Boot up LM Studio (Inference Layer)
To ensure image-vision and explanation generation runs effectively offline:
1. Open **LM Studio**.
2. Download a **Vision Model** (e.g. `Qwen-VL 4B` or `Gemma-3-4B`) and a **Reasoning Model** (e.g. `DeepSeek-R1-8B`).
3. Start the **Local Server** on port `1234`. The FastApi endpoint dynamically queries this network for the correct multimodal capacities!

### 2. Boot the API Layer
```bash
# Navigate to the backend directory
cd backend

# Activate your virtual environment
.\venv\Scripts\Activate

# Install dependencies if you haven't natively
pip install -r requirements.txt

# Start the uvicorn API server
# NOTE: The server downloads the BART-MNLI weights on the first boot-up!
uvicorn main:app --reload
```

### 3. Boot the React Dashboard
```bash
# Open a new terminal and navigate to the UI directory
cd frontend

# Install exact UI dependencies
npm install

# Start the development server (Defaults to Port 3000)
npm start
```

### 4. Load the Chrome Extension
1. Open Google Chrome and traverse to `chrome://extensions/`
2. Toggle **Developer Mode** ON.
3. Click "Load unpacked" and select the `VIT_Hackathon/extension/` folder.
4. Pin it to your browser and right click any text on the internet to test!

---

<div align="center">
  <i>Engineered for the 24Hr VIT Hackathon.</i>
</div>
