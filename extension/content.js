// content.js
console.log("OSINT Verify: Content script loaded.");

// Listen for highlighting or other page-side tasks
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "highlightMisinformation") {
    // This would use a list of claims from the database/API to highlight on-page.
    // For now, a placeholder logic
    console.log("Highlighting misinformation on the page...");
    sendResponse({ status: "done" });
  }
});

// Example function to inject highlighting — only for very specific verified claims
function highlightText(text, color) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    let node;
    while(node = walker.nextNode()) {
        if (node.textContent.includes(text)) {
            const span = document.createElement('span');
            span.style.backgroundColor = color;
            span.style.padding = '2px';
            span.style.borderRadius = '3px';
            span.textContent = text;
            
            const range = document.createRange();
            range.selectNode(node);
            // This is simplified; real implementation needs careful node splitting
        }
    }
}
