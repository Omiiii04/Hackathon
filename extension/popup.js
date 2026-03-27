document.addEventListener('DOMContentLoaded', function() {
    const inputSection = document.getElementById('input-section');
    const progressSection = document.getElementById('progress-section');
    const verdictSection = document.getElementById('verdict-section');
    
    const claimInput = document.getElementById('claim-input');
    const verifyBtn = document.getElementById('verify-btn');
    const resetBtn = document.getElementById('reset-btn');
    
    const progressBar = document.getElementById('progress-bar');
    const statusMessage = document.getElementById('status-message');
    
    const verdictBadge = document.getElementById('verdict-badge');
    const confidenceValue = document.getElementById('confidence-value');
    const explanation = document.getElementById('explanation');
    const sourcesList = document.getElementById('sources-list');

    const API_BASE = "http://localhost:8000";

    // Auto-check for claim if opened from context menu
    chrome.runtime.sendMessage({ action: "getClaim" }, (response) => {
        if (response && response.claim) {
            claimInput.value = response.claim;
            // Optionally auto-trigger verification
            // verifyBtn.click();
        }
    });

    verifyBtn.addEventListener('click', async function() {
        const claim = claimInput.value.trim();
        if (!claim) return;

        // UI State: Show progress
        inputSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        
        // Step 1: Call API
        try {
            updateProgress(10, "Initializing verification...");
            
            const response = await fetch(`${API_BASE}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ claim: claim })
            });
            
            if (!response.ok) throw new Error("API call failed");
            
            const data = await response.json();
            
            // Direct result from backend for testing (no job_id/WS needed)
            progressSection.classList.add('hidden');
            verdictSection.classList.remove('hidden');
            displayResult(data);
            
        } catch (error) {
            updateProgress(0, "Error: " + error.message);
            setTimeout(() => resetUI(), 3000);
        }
    });

    resetBtn.addEventListener('click', resetUI);

    // WebSocket disabled for basic backend testing - re-enable when backend supports ws/job_id
    /*
    function connectWebSocket(jobId) {
        const ws = new WebSocket(`ws://localhost:8000/ws/${jobId}`);
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            updateProgress(data.progress, data.message);
            
            if (data.stage === "complete") {
                ws.close();
                displayResult(data);
            }
        };
        
        ws.onerror = (error) => {
            console.error("WS Error:", error);
            updateProgress(0, "Connection error.");
        };
    }
    */

    function updateProgress(percent, message) {
        progressBar.style.width = percent + '%';
        statusMessage.textContent = message;
    }

    async function simulateProgress() {
        const stages = [
            { p: 20, m: "Parsing claim and extracting entities..." },
            { p: 40, m: "Searching for evidence across sources..." },
            { p: 60, m: "Extracting evidence from articles..." },
            { p: 80, m: "Computing weighted scores and verdict..." },
            { p: 95, m: "Generating human-readable explanation..." },
            { p: 100, m: "Verification complete." }
        ];

        for (const stage of stages) {
            updateProgress(stage.p, stage.m);
            await new Promise(resolve => setTimeout(resolve, 800));
        }
    }

    function displayResult(result) {
        progressSection.classList.add('hidden');
        verdictSection.classList.remove('hidden');
        
        verdictBadge.textContent = result.verdict;
        verdictBadge.className = 'badge ' + 'verdict-' + result.verdict.toLowerCase();
        
        confidenceValue.textContent = (result.confidence * 100).toFixed(0) + '%';
        explanation.textContent = result.explanation;
        
        // Render Sub-claims if any
        const subclaimsContainer = document.getElementById('subclaims-container');
        subclaimsContainer.innerHTML = '';
        if (result.sub_claims && result.sub_claims.length > 0 && result.is_compound) {
            const heading = document.createElement('h3');
            heading.textContent = "Claim Breakdown";
            heading.style.fontSize = "14px";
            heading.style.marginTop = "16px";
            subclaimsContainer.appendChild(heading);
            
            const icons = {
                TRUE: "✅", FALSE: "❌", MISLEADING: "⚠️",
                CONFLICTING: "🔀", UNVERIFIED: "❓"
            };
            
            result.sub_claims.forEach(sc => {
                const div = document.createElement('div');
                div.style.fontSize = "12px";
                div.style.padding = "4px 0";
                div.innerHTML = `${icons[sc.verdict] || "•"} ${sc.text} — <strong>${sc.verdict}</strong>`;
                subclaimsContainer.appendChild(div);
            });
        }
        
        sourcesList.innerHTML = '';
        result.sources.forEach(source => {
            const li = document.createElement('li');
            li.innerHTML = `<a href="${source.url}" target="_blank">${source.name}</a> — ${source.stance}`;
            sourcesList.appendChild(li);
        });
    }

    function resetUI() {
        inputSection.classList.remove('hidden');
        progressSection.classList.add('hidden');
        verdictSection.classList.add('hidden');
        claimInput.value = '';
        updateProgress(0, "Initializing...");
    }

    function getMockResult(claim) {
        // Return a mock result for the demo if no real backend is reachable
        return {
            verdict: "FALSE",
            confidence: 0.84,
            explanation: "Multiple high-credibility sources, including Reuters and AP News, contradict this claim. The information cited appears to be based on an old report that was later retracted.",
            sources: [
                { name: "Reuters", url: "https://reuters.com", stance: "CONTRADICTING" },
                { name: "AP News", url: "https://apnews.com", stance: "CONTRADICTING" },
                { name: "BBC News", url: "https://bbc.com", stance: "NEUTRAL" }
            ]
        };
    }
});
