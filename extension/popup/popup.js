// popup/popup.js — OSINT Verifier Popup Controller

const API_BASE = "http://localhost:8000";

// ─── DOM Refs ────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const claimInput   = $("claim-input");
const charCount    = $("char-count");
const imageFileInput = $("image-file-input");
const imagePreview   = $("image-preview");
const imagePreviewWrap = $("image-preview-wrap");
const uploadArea   = $("upload-area");
const imageUrlInput = $("image-url-input");
const urlInput     = $("url-input");
const progressSection = $("progress-section");
const progressStage   = $("progress-stage");
const progressBar     = $("progress-bar");
const resultSection   = $("result-section");
const errorSection    = $("error-section");

let selectedImageBase64 = null;
let lastPayload = null;

// ─── Init ────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupButtons();
  setupImageUpload();
  checkBackendStatus();
  checkPendingVerification();

  claimInput.addEventListener("input", () => {
    charCount.textContent = claimInput.value.length;
  });
});

// ─── Check for right-click pending verification ───────────────────────────────
async function checkPendingVerification() {
  const pending = await chrome.runtime.sendMessage({ type: "GET_PENDING" });
  if (!pending) return;

  if (pending.type === "text") {
    switchTab("text");
    claimInput.value = pending.claim;
    charCount.textContent = pending.claim.length;
    await runVerification(pending);
  } else if (pending.type === "image") {
    switchTab("image");
    imageUrlInput.value = pending.imageUrl;
    await runVerification(pending);
  } else if (pending.type === "url") {
    switchTab("url");
    urlInput.value = pending.url;
    await runVerification(pending);
  }
}

// ─── Backend Status Check ─────────────────────────────────────────────────────
async function checkBackendStatus() {
  const dot = $("status-dot");
  try {
    const resp = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    dot.className = resp.ok ? "status-dot online" : "status-dot offline";
    dot.title = resp.ok ? "Backend online" : "Backend returned error";
  } catch {
    dot.className = "status-dot offline";
    dot.title = "Backend offline — start the FastAPI server";
  }
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => switchTab(tab.dataset.tab));
  });
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach(t =>
    t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach(p =>
    p.classList.toggle("active", p.id === `tab-${name}`));
}

// ─── Buttons ──────────────────────────────────────────────────────────────────
function setupButtons() {
  $("verify-text-btn").addEventListener("click", async () => {
    const claim = claimInput.value.trim();
    if (!claim) return shake(claimInput);
    await runVerification({ type: "text", claim });
  });

  $("verify-image-btn").addEventListener("click", async () => {
    const url = imageUrlInput.value.trim();
    if (selectedImageBase64) {
      await runVerification({ type: "image", imageData: selectedImageBase64 });
    } else if (url) {
      await runVerification({ type: "image", imageUrl: url });
    } else {
      shake(uploadArea);
    }
  });

  $("verify-url-btn").addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) return shake(urlInput);
    await runVerification({ type: "url", url });
  });

  $("use-current-btn").addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url) {
      urlInput.value = tab.url;
      await runVerification({ type: "url", url: tab.url });
    }
  });

  $("open-full-btn").addEventListener("click", () => {
    chrome.tabs.create({ url: `${API_BASE}/dashboard` });
  });

  $("retry-btn").addEventListener("click", () => {
    if (lastPayload) runVerification(lastPayload);
  });

  $("remove-img-btn").addEventListener("click", () => {
    selectedImageBase64 = null;
    imagePreviewWrap.style.display = "none";
    uploadArea.style.display = "block";
    imageFileInput.value = "";
  });
}

// ─── Image Upload ─────────────────────────────────────────────────────────────
function setupImageUpload() {
  uploadArea.addEventListener("click", () => imageFileInput.click());

  imageFileInput.addEventListener("change", () => {
    const file = imageFileInput.files[0];
    if (file) processImageFile(file);
  });

  uploadArea.addEventListener("dragover", e => {
    e.preventDefault();
    uploadArea.classList.add("drag-over");
  });
  uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("drag-over"));
  uploadArea.addEventListener("drop", e => {
    e.preventDefault();
    uploadArea.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) processImageFile(file);
  });
}

function processImageFile(file) {
  const reader = new FileReader();
  reader.onload = () => {
    selectedImageBase64 = reader.result; // data:image/...;base64,...
    imagePreview.src = reader.result;
    imagePreviewWrap.style.display = "flex";
    uploadArea.style.display = "none";
  };
  reader.readAsDataURL(file);
}

// ─── Verification Runner ──────────────────────────────────────────────────────
async function runVerification(payload) {
  lastPayload = payload;
  showSection("progress");
  setProgress("Parsing claim…", 8);

  // UX buffer stages (FR-68)
  const stages = [
    ["Querying OSINT sources…", 20],
    ["Checking fact databases…", 38],
    ["Running stance classifier…", 55],
    ["Scoring evidence…", 70],
    ["Computing verdict…", 82],
    ["Generating explanation…", 90],
  ];

  const stageTimer = runProgressStages(stages);

  try {
    let response;
    if (payload.type === "image") {
      response = await chrome.runtime.sendMessage({
        type: "VERIFY_IMAGE",
        payload: {
          imageUrl: payload.imageUrl || payload.imageData,
          pageUrl: ""
        }
      });
    } else {
      response = await chrome.runtime.sendMessage({
        type: "VERIFY_CLAIM",
        payload
      });
    }

    clearInterval(stageTimer);
    setProgress("Verdict ready.", 100);
    await sleep(300);

    if (!response || !response.success) {
      showError(response?.error || "Backend returned an error. Is the server running?");
      return;
    }

    renderResult(response.data, payload.type);
  } catch (err) {
    clearInterval(stageTimer);
    showError(`Connection failed: ${err.message}. Make sure the FastAPI backend is running on localhost:8000.`);
  }
}

// ─── Progress Simulation ──────────────────────────────────────────────────────
function runProgressStages(stages) {
  let i = 0;
  return setInterval(() => {
    if (i < stages.length) {
      setProgress(stages[i][0], stages[i][1]);
      i++;
    }
  }, 280);
}

function setProgress(label, pct) {
  progressStage.textContent = label;
  progressBar.style.width = `${pct}%`;
}

// ─── Render Result ────────────────────────────────────────────────────────────
function renderResult(data, inputType) {
  showSection("result");

  const verdict    = data.verdict || "UNVERIFIED";
  const conf       = data.confidence ?? 0;
  const tag        = data.verdict_reason_tag || "";
  const exp        = data.explanation || "No explanation available.";
  const cached     = data.cached || false;
  const mutation   = data.mutation_detected || false;
  const mutText    = data.mutation_description || "";
  const subclaims  = data.sub_claims || [];
  const sources    = data.sources || [];
  const suppPct    = data.support_bar?.support_pct ?? null;
  const contrPct   = data.support_bar?.contradict_pct ?? null;
  const totalEv    = data.total_evidence_items ?? -1;
  const imgResult  = data.image_result || null;

  // Verdict badge
  const { emoji, cls } = verdictMeta(verdict);
  $("verdict-badge").innerHTML =
    `<span class="badge ${cls}">${emoji} ${verdict}</span>`;
  $("verdict-confidence").textContent = `Confidence: ${Math.round(conf * 100)}%`;
  $("verdict-tag").textContent = tag;

  // Mutation
  if (mutation) {
    $("mutation-alert").style.display = "block";
    $("mutation-text").textContent = mutText;
  }

  // Support bar (FR-157..160)
  const noEvidence = verdict === "UNVERIFIED" && totalEv === 0;
  if (noEvidence || suppPct === null) {
    $("support-bar-wrap").querySelector(".bar-track").style.display = "none";
    $("support-bar-wrap").querySelector(".bar-legend").style.display = "none";
    $("no-evidence-state").style.display = "block";
  } else {
    $("support-fill").style.width    = `${suppPct}%`;
    $("contradict-fill").style.width = `${contrPct}%`;
    $("support-pct").textContent     = `✅ ${suppPct}%`;
    $("contradict-pct").textContent  = `❌ ${contrPct}%`;
  }

  // Explanation
  $("explanation-text").textContent = exp;

  // Sub-claims (FR-73..78)
  if (subclaims.length > 0) {
    $("subclaims-wrap").style.display = "block";
    const list = $("subclaims-list");
    list.innerHTML = "";
    subclaims.forEach(sc => {
      const { emoji } = verdictMeta(sc.verdict);
      list.innerHTML += `<div class="sc-item">
        <span class="sc-emoji">${emoji}</span>
        <span class="sc-text">${sc.claim_text}</span>
        <span class="sc-conf">${Math.round((sc.confidence || 0) * 100)}%</span>
      </div>`;
    });
  }

  // Image results
  if (inputType === "image" && imgResult) {
    $("image-result-wrap").style.display = "block";
    if (imgResult.ocr_text) {
      $("ocr-text-result").textContent = `📄 OCR: ${imgResult.ocr_text.slice(0, 200)}`;
    }
    if (imgResult.context_mismatch) {
      $("context-mismatch-result").textContent =
        `🕐 Context Mismatch: ${imgResult.mismatch_description || "Image predates claimed event."}`;
    }
  }

  // Sources
  const srcList = $("sources-list");
  srcList.innerHTML = "";
  sources.slice(0, 4).forEach(src => {
    const stanceIcon = src.stance === "SUPPORTING" ? "✅" : src.stance === "CONTRADICTING" ? "❌" : "➖";
    srcList.innerHTML += `<div class="src-item">
      <div>
        ${stanceIcon}
        <a href="${src.url}" target="_blank" class="src-name">${src.name || src.url}</a>
      </div>
      <div class="src-meta">Tier ${src.tier ?? "?"} · ${((src.credibility ?? 0) * 100).toFixed(0)}% credible</div>
    </div>`;
  });

  // Cached
  if (cached) $("cached-label").style.display = "block";
}

// ─── Utilities ────────────────────────────────────────────────────────────────
function showSection(name) {
  progressSection.style.display = name === "progress" ? "block" : "none";
  resultSection.style.display   = name === "result"   ? "flex"  : "none";
  errorSection.style.display    = name === "error"    ? "block" : "none";
}

function showError(msg) {
  showSection("error");
  $("error-msg").textContent = msg;
}

function verdictMeta(verdict) {
  const map = {
    TRUE:        { emoji: "✅", cls: "v-true"        },
    FALSE:       { emoji: "❌", cls: "v-false"       },
    MISLEADING:  { emoji: "⚠️", cls: "v-misleading"  },
    CONFLICTING: { emoji: "🔀", cls: "v-conflicting" },
    UNVERIFIED:  { emoji: "❓", cls: "v-unverified"  }
  };
  return map[verdict] || { emoji: "❓", cls: "v-unverified" };
}

function shake(el) {
  el.style.animation = "none";
  el.style.borderColor = "#ef4444";
  setTimeout(() => el.style.borderColor = "", 1500);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
