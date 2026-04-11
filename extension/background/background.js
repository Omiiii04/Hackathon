// background/background.js
// OSINT Rumor Verifier — Service Worker
// Handles context menus, API calls, and message routing

const API_BASE = "http://localhost:8000"; // FastAPI backend
const WS_BASE  = "ws://localhost:8000";

// ─── Context Menu Setup ─────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  // Text verification
  chrome.contextMenus.create({
    id: "verify-text",
    title: "🔍 Verify Claim",
    contexts: ["selection"]
  });

  // Image scanning
  chrome.contextMenus.create({
    id: "verify-image",
    title: "🖼️ Scan & Verify Image",
    contexts: ["image"]
  });

  // Link/URL verification
  chrome.contextMenus.create({
    id: "verify-link",
    title: "🔗 Verify Linked Article",
    contexts: ["link"]
  });

  // Page-level — verify current page headline
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
      openPanel(tab, { type: "text", claim });
      break;
    }
    case "verify-image": {
      const imageUrl = info.srcUrl;
      if (!imageUrl) return;
      openPanel(tab, { type: "image", imageUrl, pageUrl: tab.url });
      break;
    }
    case "verify-link": {
      const url = info.linkUrl;
      if (!url) return;
      openPanel(tab, { type: "url", url });
      break;
    }
    case "verify-page": {
      openPanel(tab, { type: "url", url: tab.url });
      break;
    }
  }
});

// ─── Open Side Panel (inject into tab) ───────────────────────────────────────

async function openPanel(tab, payload) {
  // Store payload so popup/panel can read it
  await chrome.storage.session.set({ pendingVerification: payload });

  // Inject panel into the page if not already present
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: injectPanel
  });

  // Send message to content script to show panel with payload
  chrome.tabs.sendMessage(tab.id, {
    type: "OPEN_PANEL",
    payload
  });
}

// This runs in the page context
function injectPanel() {
  if (document.getElementById("osint-verifier-panel")) return; // already injected
}

// ─── Message Listener (from content / popup) ─────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "VERIFY_CLAIM") {
    handleVerification(msg.payload).then(sendResponse);
    return true; // keep channel open for async
  }
  if (msg.type === "VERIFY_IMAGE") {
    handleImageVerification(msg.payload).then(sendResponse);
    return true;
  }
  if (msg.type === "GET_PENDING") {
    chrome.storage.session.get("pendingVerification").then(result => {
      sendResponse(result.pendingVerification || null);
      chrome.storage.session.remove("pendingVerification");
    });
    return true;
  }
});

// ─── Text/URL Verification ────────────────────────────────────────────────────

async function handleVerification(payload) {
  try {
    const body = payload.type === "url"
      ? { url: payload.url }
      : { claim: payload.claim };

    const endpoint = payload.type === "url"
      ? `${API_BASE}/verify/url`
      : `${API_BASE}/verify/text`;

    const resp = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      const err = await resp.text();
      return { success: false, error: `Server error ${resp.status}: ${err}` };
    }

    const data = await resp.json();
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

// ─── Image Verification ───────────────────────────────────────────────────────

async function handleImageVerification(payload) {
  try {
    let imageData;

    if (payload.imageUrl.startsWith("data:")) {
      // Already base64
      imageData = payload.imageUrl;
    } else {
      // Fetch image and convert to base64
      const imgResp = await fetch(payload.imageUrl);
      const blob = await imgResp.blob();
      imageData = await blobToBase64(blob);
    }

    const body = {
      image_base64: imageData,
      source_url: payload.imageUrl,
      page_url: payload.pageUrl || ""
    };

    const resp = await fetch(`${API_BASE}/verify/image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (!resp.ok) {
      const err = await resp.text();
      return { success: false, error: `Server error ${resp.status}: ${err}` };
    }

    const data = await resp.json();
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// ─── WebSocket Helper (for content script to use via messaging) ───────────────
// The content script can't open WebSockets itself cleanly cross-origin in MV3,
// so we proxy WS events through the service worker.

const wsConnections = {};

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
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
      chrome.tabs.sendMessage(sender.tab.id, {
        type: "WS_ERROR",
        taskId
      });
    };

    ws.onclose = () => {
      chrome.tabs.sendMessage(sender.tab.id, {
        type: "WS_CLOSE",
        taskId
      });
      delete wsConnections[taskId];
    };

    sendResponse({ connected: true });
    return true;
  }
});
