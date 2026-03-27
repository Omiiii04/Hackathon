// background.js

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verifyClaim",
    title: "Verify Claim",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "verifyClaim") {
    const selectedText = info.selectionText;
    
    // Store the selection temporarily
    chrome.storage.local.set({ lastSelectedClaim: selectedText }, () => {
      // Open the popup or send a message
      chrome.action.openPopup();
    });
  }
});

// Handle messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getClaim") {
    chrome.storage.local.get(["lastSelectedClaim"], (result) => {
      sendResponse({ claim: result.lastSelectedClaim });
      // Clear after retrieval
      chrome.storage.local.remove(["lastSelectedClaim"]);
    });
    return true; // Keep channel open for async response
  }
});
