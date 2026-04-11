# OSINT Rumor Verifier — Chrome Extension

**Version 5.2.0 · Radio Frequency Team · VIT Code Apex 2.0**

A Chrome extension for the OSINT Rumor Verification Platform that lets you **right-click any text, image, or link** on any webpage to instantly verify claims, scan images for OCR + reverse-image evidence, and view structured verdicts with support/contradict ratios.

---

## Features

| Feature | Description |
|---|---|
| ✅ **Right-click text** | Select any text → "Verify Claim" |
| 🖼️ **Right-click image** | Right-click any image → "Scan & Verify Image" |
| 🔗 **Right-click link** | Right-click any link → "Verify Linked Article" |
| 📰 **Right-click page** | Right-click anywhere → "Verify This Page" |
| 📝 **Popup: Text tab** | Paste any claim manually |
| 🖼️ **Popup: Image tab** | Upload or paste image URL for scanning |
| 🔗 **Popup: URL tab** | Enter or auto-fill current page URL |
| 📊 **5 Verdict classes** | TRUE / FALSE / MISLEADING / CONFLICTING / UNVERIFIED |
| 🔀 **Sub-claim breakdown** | Compound claims split and shown per part |
| 📈 **Support/Contradict bar** | Visual evidence split per verdict |
| ⚠️ **Mutation alerts** | Warns if claim is part of a known misinformation chain |
| ⚡ **UX buffering** | Simulates pipeline progress (no "instant answer distrust") |
| 🕐 **Context mismatch** | Flags recycled images used out of original context |
| 📄 **OCR extraction** | Text extracted from images via EasyOCR |

---

## Setup

### 1. Install the Extension in Chrome

1. Open Chrome and go to `chrome://extensions`
2. Enable **Developer Mode** (toggle in top-right)
3. Click **"Load unpacked"**
4. Select the `osint-extension/` folder
5. The 🔍 icon will appear in your toolbar

### 2. Start the Backend

Make sure the FastAPI backend is running:

```bash
# From your project root
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The extension connects to `http://localhost:8000` by default.

---

## Usage

### Right-Click Verification (Context Menu)

1. **Verify Text** — Select any text on a webpage → right-click → **"🔍 Verify Claim"**
2. **Scan Image** — Right-click any image → **"🖼️ Scan & Verify Image"**
3. **Verify Link** — Right-click any hyperlink → **"🔗 Verify Linked Article"**
4. **Verify Page** — Right-click anywhere → **"📰 Verify This Page"**

A side panel slides in from the right with live progress and the result.

### Popup Verification

Click the 🔍 icon in the toolbar to open the popup:
- **Text tab** — Paste a claim (up to 2000 chars)
- **Image tab** — Upload a JPEG/PNG/WEBP or paste an image URL
- **URL tab** — Enter a URL, or click "Use Current Page"

---

## Extension File Structure

```
osint-extension/
├── manifest.json              # Chrome Extension Manifest v3
├── background/
│   └── background.js          # Service worker: context menus, API calls, WS proxy
├── content/
│   ├── content.js             # Side panel injected into every webpage
│   └── content.css            # Side panel styles
├── popup/
│   ├── popup.html             # Extension toolbar popup
│   ├── popup.css              # Popup styles
│   └── popup.js               # Popup logic: tabs, image upload, result render
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

---

## Backend API Endpoints Used

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Backend status check (green dot) |
| `POST` | `/verify/text` | Verify a text claim |
| `POST` | `/verify/url` | Verify an article URL |
| `POST` | `/verify/image` | Image OCR + reverse search + verdict |
| `WS` | `/ws/{task_id}` | Realtime pipeline progress stream |

### Request Formats

**Text:**
```json
POST /verify/text
{ "claim": "NASA confirmed alien life" }
```

**URL:**
```json
POST /verify/url
{ "url": "https://example.com/article" }
```

**Image:**
```json
POST /verify/image
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
  "source_url": "https://example.com/image.jpg",
  "page_url": "https://example.com"
}
```

### Response Format

```json
{
  "verdict": "FALSE",
  "confidence": 0.87,
  "verdict_reason_tag": "Widely debunked",
  "explanation": "Multiple Tier-1 sources contradict this claim...",
  "top_insight": "Reuters reported no such announcement was made.",
  "cached": false,
  "mutation_detected": false,
  "total_evidence_items": 12,
  "support_bar": {
    "support_pct": 14,
    "contradict_pct": 86
  },
  "sub_claims": [
    {
      "claim_text": "NASA held a press conference",
      "verdict": "FALSE",
      "confidence": 0.91
    }
  ],
  "sources": [
    {
      "name": "Reuters",
      "url": "https://reuters.com/...",
      "tier": 1,
      "credibility": 0.95,
      "stance": "CONTRADICTING",
      "snippet": "No such announcement was made...",
      "credibility_shift": -0.02
    }
  ],
  "image_result": {
    "ocr_text": "Breaking: Scientists discover...",
    "reverse_search_matches": [],
    "context_mismatch": true,
    "mismatch_description": "Image first appeared in 2019, predates claimed 2024 event."
  }
}
```

---

## Configuration

To change the backend URL, edit the top of these files:
- `background/background.js` → `const API_BASE`
- `popup/popup.js` → `const API_BASE`

---

## Verdict Color Reference

| Verdict | Color | Meaning |
|---|---|---|
| ✅ TRUE | Green | Supported by ≥2 Tier-1 sources |
| ❌ FALSE | Red | Contradicted by ≥2 Tier-1 sources |
| ⚠️ MISLEADING | Yellow | Temporal mismatch or deceptive framing |
| 🔀 CONFLICTING | Purple | Tier-1 sources genuinely divided |
| ❓ UNVERIFIED | Gray | Insufficient credible sources found |

---

*OSINT Rumor Verification Platform · SRS v5.2.0 · Radio Frequency Team*
