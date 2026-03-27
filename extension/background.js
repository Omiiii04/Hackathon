// background.js

let osintWindowId = null;   // track our persistent window

// ── Open or focus the OSINT window when the toolbar icon is clicked ──
chrome.action.onClicked.addListener(() => {
  openOsintWindow();
});

function openOsintWindow(claim) {
  // If we already have a window open, just focus it
  if (osintWindowId !== null) {
    chrome.windows.get(osintWindowId, (win) => {
      if (chrome.runtime.lastError || !win) {
        // Window no longer exists — create a new one
        osintWindowId = null;
        createWindow(claim);
      } else {
        chrome.windows.update(osintWindowId, { focused: true });
      }
    });
  } else {
    createWindow(claim);
  }
}

function createWindow(claim) {
  chrome.windows.create({
    url:    chrome.runtime.getURL('popup.html'),
    type:   'popup',          // standalone window — won't close on outside clicks
    width:  400,
    height: 640,
    focused: true
  }, (win) => {
    osintWindowId = win.id;
  });

  // Store claim if we were launched from the context menu
  if (claim) {
    chrome.storage.local.set({ lastSelectedClaim: claim });
  }
}

// When our window is closed by the X button (window.close), clear the id
chrome.windows.onRemoved.addListener((windowId) => {
  if (windowId === osintWindowId) {
    osintWindowId = null;
  }
});

// ── Context menu ─────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id:       'verifyClaim',
    title:    'Verify with OSINT',
    contexts: ['selection']
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId === 'verifyClaim') {
    chrome.storage.local.set({ lastSelectedClaim: info.selectionText }, () => {
      openOsintWindow(info.selectionText);
    });
  }
});

// ── Message handler ───────────────────────────────────────────────────
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getClaim') {
    chrome.storage.local.get(['lastSelectedClaim'], (result) => {
      sendResponse({ claim: result.lastSelectedClaim || '' });
      chrome.storage.local.remove(['lastSelectedClaim']);
    });
    return true;   // keep channel open for async response
  }
});
