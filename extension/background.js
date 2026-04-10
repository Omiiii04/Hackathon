// background/background.js
// OSINT Rumor Verifier — Service Worker
// Handles context menus, API calls, and message routing

const API_BASE = "http://localhost:8000";
const WS_BASE  = "ws://localhost:8000";

// ─── Context Menu Setup ──────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verify-text",
    title: "🔍 Verify Claim",
    contexts: ["selection"]
  });
  chrome.contextMenus.create({
    id: "verify-image",
    title: "🖼️ Scan & Verify Image",
    contexts: ["image"]
  });
  chrome.contextMenus.create({
    id: "verify-link",
    title: "🔗 Verify Linked Article",
    contexts: ["link"]
  });
  chrome.contextMenus.create({
    id: "verify-page",
    title: "📰 Verify This Page",
    contexts: ["page"]
  });
});

// ─── Context Menu Click Handler ──────────────────────────────────────────────

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  switch (info.menuItemId) {
    case "verify-text": {
      const claim = info.selectionText?.trim();
      if (!claim) return;
      await openPanel(tab, { type: "text", claim });
      break;
    }
    case "verify-image": {
      const imageUrl = info.srcUrl;
      if (!imageUrl) return;
      await openPanel(tab, { type: "image", imageUrl, pageUrl: tab.url });
      break;
    }
    case "verify-link": {
      const url = info.linkUrl;
      if (!url) return;
      await openPanel(tab, { type: "url", url });
      break;
    }
    case "verify-page": {
      await openPanel(tab, { type: "url", url: tab.url });
      break;
    }
  }
});

// ─── Open Side Panel ─────────────────────────────────────────────────────────
// BUG FIX: The old code called executeScript (which does nothing useful since
// content scripts are already declared in manifest.json) then immediately sent
// a message — but the content script might not be ready yet, so the message
// was silently dropped.
// FIX: Store payload in session storage and use a retry loop to send the
// message, so it works even if the content script needs a moment to initialise.

async function openPanel(tab, payload) {
  // Persist payload so content script can poll for it if message missed
  await chrome.storage.session.set({ pendingVerification: payload });

  // Ensure content script is injected (safe to call even if already injected —
  // the IIFE guard `window.__osintInjected` prevents double-init)
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content/content.js"]
    });
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ["content/content.css"]
    });
  } catch (_) {
    // Already injected or restricted page — ignore
  }

  // Retry sending message up to 5 times with 150ms gaps to survive
  // the brief window between injection and the listener being registered
  let sent = false;
  for (let attempt = 0; attempt < 5; attempt++) {
    await sleep(150);
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "OPEN_PANEL", payload });
      sent = true;
      break;
    } catch (_) {
      // Content script not ready yet — retry
    }
  }

  if (!sent) {
    // Last resort: content script will pick up payload via GET_PENDING on next
    // message exchange, or user can click the extension icon
    console.warn("OSINT: Could not deliver OPEN_PANEL message to tab", tab.id);
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ─── SINGLE unified message listener ─────────────────────────────────────────
// BUG FIX: The original code registered TWO separate onMessage listeners.
// In MV3 service workers only the FIRST listener reliably handles a given
// message type — the second listener (WS_CONNECT) was completely dead.
// FIX: Merge everything into one listener.

const wsConnections = {};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {

  // ── Verification ──
  if (msg.type === "VERIFY_CLAIM") {
    handleVerification(msg.payload).then(sendResponse);
    return true;
  }

  if (msg.type === "VERIFY_IMAGE") {
    handleImageVerification(msg.payload).then(sendResponse);
    return true;
  }

  // ── Pending payload (popup polls this on open) ──
  if (msg.type === "GET_PENDING") {
    chrome.storage.session.get("pendingVerification").then(result => {
      sendResponse(result.pendingVerification || null);
      chrome.storage.session.remove("pendingVerification");
    });
    return true;
  }

  // ── WebSocket proxy ──
  if (msg.type === "WS_CONNECT") {
    const { taskId } = msg;
    const ws = new WebSocket(`${WS_BASE}/ws/${taskId}`);
    wsConnections[taskId] = ws;

    ws.onmessage = (event) => {
      chrome.tabs.sendMessage(sender.tab.id, {
        type: "WS_MESSAGE",
        taskId,
        data: JSON.parse(event.data)
      });
    };
    ws.onerror = () => {
      chrome.tabs.sendMessage(sender.tab.id, { type: "WS_ERROR", taskId });
    };
    ws.onclose = () => {
      chrome.tabs.sendMessage(sender.tab.id, { type: "WS_CLOSE", taskId });
      delete wsConnections[taskId];
    };

    sendResponse({ connected: true });
    return true;
  }
});

// ─── Text / URL Verification ──────────────────────────────────────────────────

async function handleVerification(payload) {
  try {
    const isUrl    = payload.type === "url";
    const body     = isUrl ? { url: payload.url } : { claim: payload.claim };
    const endpoint = isUrl ? `${API_BASE}/verify/url` : `${API_BASE}/verify/text`;

    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      const err = await resp.text();
      return { success: false, error: `Server error ${resp.status}: ${err}` };
    }

    return { success: true, data: await resp.json() };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// ─── Image Verification ───────────────────────────────────────────────────────

async function handleImageVerification(payload) {
  try {
    let imageData;

    if (!payload.imageUrl) {
      return { success: false, error: "No image URL or data provided." };
    }

    if (payload.imageUrl.startsWith("data:")) {
      imageData = payload.imageUrl;
    } else {
      const imgResp = await fetch(payload.imageUrl);
      const blob    = await imgResp.blob();
      imageData     = await blobToBase64(blob);
    }

    const resp = await fetch(`${API_BASE}/verify/image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_base64: imageData,
        source_url: payload.imageUrl,
        page_url: payload.pageUrl || ""
      })
    });

    if (!resp.ok) {
      const err = await resp.text();
      return { success: false, error: `Server error ${resp.status}: ${err}` };
    }

    return { success: true, data: await resp.json() };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror   = reject;
    reader.readAsDataURL(blob);
  });
}