// content/content.js


(function () {
  if (window.__osintInjected) return;
  window.__osintInjected = true;

  // ─── Panel State ─────────────────────────────────────────────────────────────
  let panelEl       = null;
  let currentPayload = null;

  // ─── Message Listener ────────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.type === "OPEN_PANEL") {
      currentPayload = msg.payload;
      showPanel();
      startVerification(msg.payload);
    }
    if (msg.type === "WS_MESSAGE") handleWsMessage(msg.data);
    if (msg.type === "WS_ERROR")   showError("WebSocket connection error.");
    if (msg.type === "WS_CLOSE")   { /* pipeline finished */ }
  });

  // This is the fallback for the race condition between injection and messaging.
  (async function pollPending() {
    try {
      const result = await chrome.runtime.sendMessage({ type: "GET_PENDING" });
      if (result) {
        currentPayload = result;
        showPanel();
        startVerification(result);
      }
    } catch (_) {
      // Extension context not yet ready — ignore
    }
  })();

  // ─── Build Panel DOM ──────────────────────────────────────────────────────────
  function showPanel() {
    if (panelEl) {
      panelEl.classList.add("osint-visible");
      resetPanel();
      return;
    }

    panelEl = document.createElement("div");
    panelEl.id = "osint-verifier-panel";
    panelEl.innerHTML = getPanelHTML();
    document.body.appendChild(panelEl);

    panelEl.querySelector("#osint-close").addEventListener("click", hidePanel);

    // It is now declared directly in the HTML template below.
    initResize();

    setTimeout(() => panelEl.classList.add("osint-visible"), 10);
  }

  function hidePanel() {
    if (panelEl) panelEl.classList.remove("osint-visible");
  }

  function resetPanel() {
    setSection("osint-progress-section", true);
    setSection("osint-result-section",   false);
    setSection("osint-error-section",    false);

    // Reseting progress bar and label
    const bar = panelEl?.querySelector("#osint-progress-bar");
    const lbl = panelEl?.querySelector("#osint-stage-label");
    if (bar) bar.style.width = "0%";
    if (lbl) lbl.textContent = "Initializing verification…";

    // Hide claim preview
    const preview = panelEl?.querySelector("#osint-claim-preview");
    if (preview) { preview.style.display = "none"; preview.innerHTML = ""; }

    // Hide mutation/cached
    const mut = panelEl?.querySelector("#osint-mutation-alert");
    if (mut) mut.style.display = "none";
    const cached = panelEl?.querySelector("#osint-cached-badge");
    if (cached) cached.style.display = "none";
  }

  function getPanelHTML() {
    return `
      <!-- BUG FIX: resize handle declared here so it stays as a positioned
           child of the panel, not breaking the flex column of panel-inner -->
      <div id="osint-resize-handle"></div>

      <div id="osint-panel-inner">
        <div id="osint-header">
          <div id="osint-title">
            <span class="osint-logo">🛡️</span>
            <span>OSINT Verifier</span>
          </div>
          <button id="osint-close" title="Close">✕</button>
        </div>

        <!-- Claim Preview -->
        <div id="osint-claim-preview"></div>

        <!-- Progress Section -->
        <div id="osint-progress-section">
          <div id="osint-stage-label">Initializing…</div>
          <div id="osint-progress-bar-wrap">
            <div id="osint-progress-bar"></div>
          </div>
          <div id="osint-substage-label"></div>
        </div>

        <!-- Result Section -->
        <div id="osint-result-section" style="display:none">

          <div id="osint-verdict-card">
            <div id="osint-verdict-badge"></div>
            <div id="osint-confidence-label"></div>
            <div id="osint-verdict-tag"></div>
          </div>

          <div id="osint-mutation-alert" style="display:none">
            ⚠️ <strong>Mutation Detected:</strong>
            <span id="osint-mutation-text"></span>
          </div>

          <div id="osint-support-bar-section">
            <div class="osint-bar-label">Support vs Contradict</div>
            <div class="osint-bar-wrap">
              <div id="osint-support-fill"    class="osint-support-fill"></div>
              <div id="osint-contradict-fill" class="osint-contradict-fill"></div>
            </div>
            <div class="osint-bar-legend">
              <span id="osint-support-pct"    class="osint-support-text"></span>
              <span id="osint-contradict-pct" class="osint-contradict-text"></span>
            </div>
            <div id="osint-no-evidence-placeholder" style="display:none">
              <div class="osint-empty-bar">No evidence collected yet</div>
            </div>
          </div>

          <div id="osint-top-insight-section">
            <div class="osint-section-heading">💡 Top Insight</div>
            <div id="osint-top-insight"></div>
          </div>

          <div id="osint-explanation-section">
            <div class="osint-section-heading">📋 Explanation</div>
            <div id="osint-explanation"></div>
          </div>

          <div id="osint-subclaims-section" style="display:none">
            <div class="osint-section-heading">🔀 Sub-Claim Breakdown</div>
            <div id="osint-subclaims-list"></div>
          </div>

          <div id="osint-image-section" style="display:none">
            <div class="osint-section-heading">🖼️ Image Scan</div>
            <div id="osint-image-ocr"></div>
            <div id="osint-image-reverse"></div>
            <div id="osint-image-context"></div>
          </div>

          <div id="osint-sources-section">
            <div class="osint-section-heading">📰 Sources</div>
            <div id="osint-sources-list"></div>
          </div>

          <div id="osint-cached-badge" style="display:none">⚡ Result from cache</div>
        </div>

        <!-- Error Section -->
        <div id="osint-error-section" style="display:none">
          <div id="osint-error-icon">⚠️</div>
          <div id="osint-error-msg"></div>
          <button id="osint-retry-btn">Retry</button>
        </div>
      </div>
    `;
  }

  // ─── Verification ─────────────────────────────────────────────────────────────
  async function startVerification(payload) {
    resetPanel();

    // Show claim preview
    const preview = panelEl.querySelector("#osint-claim-preview");
    if (payload.type === "text") {
      preview.textContent = `"${payload.claim.slice(0, 120)}${payload.claim.length > 120 ? "…" : ""}"`;
      preview.style.display = "block";
    } else if (payload.type === "image") {
      preview.innerHTML = `<img src="${payload.imageUrl}" alt="Image to verify"
        style="max-width:100%;border-radius:6px;margin-top:4px;">`;
      preview.style.display = "block";
    } else if (payload.type === "url") {
      preview.textContent = `🔗 ${(payload.url || "").slice(0, 80)}…`;
      preview.style.display = "block";
    }

    await simulateProgress();
    updateProgress("Contacting verification engine…", 80);

    let result;
    try {
      if (payload.type === "image") {
        result = await chrome.runtime.sendMessage({ type: "VERIFY_IMAGE", payload });
      } else {
        result = await chrome.runtime.sendMessage({ type: "VERIFY_CLAIM", payload });
      }
    } catch (err) {
      showError(`Could not reach background service: ${err.message}`);
      return;
    }

    updateProgress("Verdict ready.", 100);
    await sleep(300);

    if (!result || !result.success) {
      showError(result?.error || "Unknown error from verification backend.");
      return;
    }

    renderResult(result.data, payload.type);
  }

  async function simulateProgress() {
    const stages = [
      ["Parsing claim…",                    10],
      ["Querying OSINT sources…",           25],
      ["Checking fact databases…",          40],
      ["Running NLI stance classifier…",    55],
      ["Scoring evidence…",                 70],
      ["Computing verdict…",                78],
    ];
    for (const [label, pct] of stages) {
      updateProgress(label, pct);
      await sleep(220 + Math.random() * 180);
    }
  }

  // ─── Render Result ────────────────────────────────────────────────────────────
  function renderResult(data, inputType) {
    setSection("osint-progress-section", false);
    setSection("osint-result-section",   true);
    setSection("osint-error-section",    false);

    const verdict    = data.verdict               || "UNVERIFIED";
    const conf       = data.confidence            ?? 0;
    const tag        = data.verdict_reason_tag    || "";
    const exp        = data.explanation           || "No explanation available.";
    const insight    = data.top_insight           || "";
    const cached     = data.cached                || false;
    const mutation   = data.mutation_detected     || false;
    const mutText    = data.mutation_description  || "";
    const subclaims  = data.sub_claims            || [];
    const sources    = data.sources               || [];
    const suppPct    = data.support_bar?.support_pct    ?? null;
    const contrPct   = data.support_bar?.contradict_pct ?? null;
    const totalEv    = data.total_evidence_items  ?? -1;
    const imgResult  = data.image_result          || null;

    // Verdict badge
    const { emoji, cls } = verdictMeta(verdict);
    panelEl.querySelector("#osint-verdict-badge").innerHTML =
      `<span class="osint-badge ${cls}">${emoji} ${verdict}</span>`;
    panelEl.querySelector("#osint-confidence-label").textContent =
      `Confidence: ${Math.round(conf * 100)}%`;
    panelEl.querySelector("#osint-verdict-tag").textContent = tag;

    // Mutation alert
    if (mutation) {
      const alert = panelEl.querySelector("#osint-mutation-alert");
      alert.style.display = "flex";
      panelEl.querySelector("#osint-mutation-text").textContent = mutText;
    }

    // Support bar
    renderSupportBar(verdict, suppPct, contrPct, totalEv);

    // Top insight
    if (insight) {
      panelEl.querySelector("#osint-top-insight").textContent = insight;
    } else {
      panelEl.querySelector("#osint-top-insight-section").style.display = "none";
    }

    // Explanation
    panelEl.querySelector("#osint-explanation").textContent = exp;

    // Sub-claims
    if (subclaims.length > 0) renderSubclaims(subclaims);

    // Image results
    if (inputType === "image" && imgResult) renderImageResults(imgResult);

    // Sources
    renderSources(sources);

    // Cached badge
    if (cached) {
      panelEl.querySelector("#osint-cached-badge").style.display = "block";
    }

    // Wire retry button (remove previous listener by cloning)
    const retryBtn = panelEl.querySelector("#osint-retry-btn");
    const newRetry = retryBtn.cloneNode(true);
    retryBtn.replaceWith(newRetry);
    newRetry.addEventListener("click", () => {
      if (currentPayload) startVerification(currentPayload);
    });

    // Scroll panel back to top
    const inner = panelEl.querySelector("#osint-panel-inner");
    if (inner) inner.scrollTop = 0;
  }

  // ─── Support Bar ──────────────────────────────────────────────────────────────
  function renderSupportBar(verdict, suppPct, contrPct, totalEv) {
    const noEvidence  = verdict === "UNVERIFIED" && totalEv === 0;
    const placeholder = panelEl.querySelector("#osint-no-evidence-placeholder");
    const barWrap     = panelEl.querySelector(".osint-bar-wrap");
    const legend      = panelEl.querySelector(".osint-bar-legend");

    if (noEvidence || suppPct === null) {
      barWrap.style.display       = "none";
      legend.style.display        = "none";
      placeholder.style.display   = "flex";
      return;
    }

    placeholder.style.display = "none";
    barWrap.style.display     = "flex";
    legend.style.display      = "flex";

    panelEl.querySelector("#osint-support-fill").style.width    = `${suppPct}%`;
    panelEl.querySelector("#osint-contradict-fill").style.width = `${contrPct}%`;
    panelEl.querySelector("#osint-support-pct").textContent     = `✅ Support ${suppPct}%`;
    panelEl.querySelector("#osint-contradict-pct").textContent  = `❌ Contradict ${contrPct}%`;
  }

  // ─── Sub-Claims ───────────────────────────────────────────────────────────────
  function renderSubclaims(subclaims) {
    const section = panelEl.querySelector("#osint-subclaims-section");
    const list    = panelEl.querySelector("#osint-subclaims-list");
    section.style.display = "block";
    list.innerHTML = "";

    subclaims.forEach(sc => {
      const { emoji } = verdictMeta(sc.verdict);
      const item = document.createElement("div");
      item.className = "osint-subclaim-item";
      item.innerHTML = `
        <span class="osint-sc-emoji">${emoji}</span>
        <span class="osint-sc-text">${sc.claim_text || sc.text || ""}</span>
        <span class="osint-sc-conf">${Math.round((sc.confidence || 0) * 100)}%</span>
      `;
      list.appendChild(item);
    });
  }

  // ─── Image Results ────────────────────────────────────────────────────────────
  function renderImageResults(imageResult) {
    panelEl.querySelector("#osint-image-section").style.display = "block";

    const ocrEl = panelEl.querySelector("#osint-image-ocr");
    const revEl = panelEl.querySelector("#osint-image-reverse");
    const ctxEl = panelEl.querySelector("#osint-image-context");

    if (imageResult.ocr_text) {
      ocrEl.innerHTML =
        `<strong>Extracted Text (OCR):</strong><blockquote>${imageResult.ocr_text.slice(0, 300)}</blockquote>`;
    }

    if (imageResult.reverse_search_matches?.length) {
      revEl.innerHTML = "<strong>Reverse Image Matches:</strong>";
      imageResult.reverse_search_matches.slice(0, 3).forEach(m => {
        revEl.innerHTML += `<div class="osint-rev-match">
          <a href="${m.url}" target="_blank" rel="noopener">${m.title || m.url}</a>
          <span class="osint-rev-date">${m.published_at || ""}</span>
        </div>`;
      });
    }

    if (imageResult.context_mismatch) {
      ctxEl.innerHTML = `<div class="osint-mismatch-alert">
        🕐 <strong>Context Mismatch:</strong>
        ${imageResult.mismatch_description || "Image predates claimed event by 30+ days."}
      </div>`;
    }
  }

  // ─── Sources ──────────────────────────────────────────────────────────────────
  function renderSources(sources) {
    const list = panelEl.querySelector("#osint-sources-list");
    list.innerHTML = "";

    if (!sources.length) {
      list.innerHTML = `<div class="osint-no-sources">No credible sources found.</div>`;
      return;
    }

    sources.slice(0, 5).forEach(src => {
      const stanceIcon = src.stance === "SUPPORTING"
        ? "✅" : src.stance === "CONTRADICTING" ? "❌" : "➖";
      const shift = src.credibility_shift
        ? `<span class="osint-cred-shift">${src.credibility_shift > 0 ? "+" : ""}${src.credibility_shift.toFixed(2)}</span>`
        : "";
      const item = document.createElement("div");
      item.className = "osint-source-item";
      item.innerHTML = `
        <div class="osint-source-header">
          ${stanceIcon}
          <a href="${src.url || "#"}" target="_blank" rel="noopener"
             class="osint-source-name">${src.name || src.url || "Unknown"}</a>
          ${shift}
        </div>
        <div class="osint-source-snippet">${(src.snippet || "").slice(0, 120)}</div>
        <div class="osint-source-meta">
          Tier ${src.tier ?? "?"} · Credibility: ${((src.credibility ?? 0) * 100).toFixed(0)}%
        </div>
      `;
      list.appendChild(item);
    });
  }

  // ─── WebSocket Realtime ───────────────────────────────────────────────────────
  function handleWsMessage(data) {
    if (data.stage) updateProgress(data.stage, data.progress ?? 50);
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────────
  function updateProgress(label, pct) {
    const lbl = panelEl?.querySelector("#osint-stage-label");
    const bar = panelEl?.querySelector("#osint-progress-bar");
    if (lbl) lbl.textContent   = label;
    if (bar) bar.style.width   = `${pct}%`;
  }

  function setSection(id, visible) {
    const el = panelEl?.querySelector(`#${id}`);
    if (el) el.style.display = visible ? "block" : "none";
  }

  function showError(msg) {
    setSection("osint-progress-section", false);
    setSection("osint-result-section",   false);
    setSection("osint-error-section",    true);
    const errEl = panelEl?.querySelector("#osint-error-msg");
    if (errEl) errEl.textContent = msg;
  }

  function verdictMeta(verdict) {
    const map = {
      TRUE:        { emoji: "✅", cls: "osint-v-true"        },
      FALSE:       { emoji: "❌", cls: "osint-v-false"       },
      MISLEADING:  { emoji: "⚠️", cls: "osint-v-misleading"  },
      CONFLICTING: { emoji: "🔀", cls: "osint-v-conflicting" },
      UNVERIFIED:  { emoji: "❓", cls: "osint-v-unverified"  }
    };
    return map[verdict] || { emoji: "❓", cls: "osint-v-unverified" };
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  // ─── Resize Handle ────────────────────────────────────────────────────────────
  function initResize() {
    const handle = panelEl.querySelector("#osint-resize-handle");
    if (!handle) return;

    let startX, startW;

    handle.addEventListener("mousedown", e => {
      startX = e.clientX;
      startW = panelEl.offsetWidth;
      e.preventDefault();

      const onDrag = e => {
        const newW = Math.max(300, Math.min(700, startW - (e.clientX - startX)));
        panelEl.style.width = `${newW}px`;
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onDrag);
        document.removeEventListener("mouseup",  onUp);
      };
      document.addEventListener("mousemove", onDrag);
      document.addEventListener("mouseup",  onUp);
    });
  }

})();