// extension/popup.js  –  Premium dark UI

document.addEventListener('DOMContentLoaded', function () {

    // ── Element refs ────────────────────────────────────
    const inputSection    = document.getElementById('input-section');
    const progressSection = document.getElementById('progress-section');
    const verdictSection  = document.getElementById('verdict-section');

    const modeTextBtn     = document.getElementById('mode-text-btn');
    const modeImageBtn    = document.getElementById('mode-image-btn');
    const wrapText        = document.getElementById('wrap-text');
    const wrapImage       = document.getElementById('wrap-image');
    
    const claimInput      = document.getElementById('claim-input');
    const charCount       = document.getElementById('char-count');
    
    const imageUploadArea = document.getElementById('image-upload-area');
    const imageFileInput  = document.getElementById('image-file-input');
    const imagePreview    = document.getElementById('image-preview');
    const imagePlaceholder= document.getElementById('image-placeholder');
    const imageFilename   = document.getElementById('image-filename');

    const verifyBtn       = document.getElementById('verify-btn');
    const resetBtn        = document.getElementById('reset-btn');

    const progressBar     = document.getElementById('progress-bar');
    const statusMessage   = document.getElementById('status-message');

    const verdictBadge    = document.getElementById('verdict-badge');
    const confidenceValue = document.getElementById('confidence-value');
    const ringFill        = document.getElementById('ring-fill');
    const explanation     = document.getElementById('explanation');
    const sourcesList     = document.getElementById('sources-list');
    const subclaimsCont   = document.getElementById('subclaims-container');

    const API_BASE = 'http://localhost:8000';
    const RING_CIRCUMFERENCE = 2 * Math.PI * 20; // r=20 → ≈125.66

    // Inject SVG gradient definition once
    injectSvgGradient();

    // ── Char counter ────────────────────────────────────
    claimInput.addEventListener('input', () => {
        charCount.textContent = claimInput.value.length;
    });

    // ── Mode Toggling ───────────────────────────────────
    let currentMode = 'text';
    let currentImageBase64 = null;
    let currentImageUrl = null;

    modeTextBtn.addEventListener('click', () => {
        currentMode = 'text';
        modeTextBtn.classList.add('active');
        modeImageBtn.classList.remove('active');
        wrapText.classList.remove('hidden');
        wrapImage.classList.add('hidden');
    });

    modeImageBtn.addEventListener('click', () => {
        currentMode = 'image';
        modeImageBtn.classList.add('active');
        modeTextBtn.classList.remove('active');
        wrapImage.classList.remove('hidden');
        wrapText.classList.add('hidden');
    });

    // ── Image Upload ─────────────────────────────────────
    imageUploadArea.addEventListener('click', () => imageFileInput.click());

    imageFileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (ev) => {
                currentImageBase64 = ev.target.result;
                currentImageUrl = null;
                imagePreview.src = currentImageBase64;
                imagePreview.classList.remove('hidden');
                imagePlaceholder.classList.add('hidden');
            };
            reader.readAsDataURL(file);
        }
    });

    // ── Auto-fill from context menu ──────────────────────
    chrome.runtime.sendMessage({ action: 'getClaim' }, (response) => {
        if (response) {
            if (response.imageUrl) {
                // Sent from context menu image click
                currentImageUrl = response.imageUrl;
                currentImageBase64 = null;
                imagePreview.src = currentImageUrl;
                imagePreview.classList.remove('hidden');
                imagePlaceholder.classList.add('hidden');
                modeImageBtn.click(); // switch to image UI
            } else if (response.claim) {
                // Sent from context menu text selection
                claimInput.value = response.claim;
                charCount.textContent = response.claim.length;
                modeTextBtn.click();
            }
        }
    });

    // ── Verify button ────────────────────────────────────
    verifyBtn.addEventListener('click', async () => {
        let payload = {};
        
        if (currentMode === 'text') {
            const claim = claimInput.value.trim();
            if (!claim) {
                claimInput.classList.add('shake');
                setTimeout(() => claimInput.classList.remove('shake'), 500);
                return;
            }
            payload = { claim: claim };
        } else {
            if (!currentImageBase64 && !currentImageUrl) {
                imageUploadArea.classList.add('shake');
                setTimeout(() => imageUploadArea.classList.remove('shake'), 500);
                return;
            }
            payload = {
                claim: "",
                image_base64: currentImageBase64,
                image_url: currentImageUrl
            };
        }

        showProgress();
        const progressDone = simulateProgress(currentMode);

        try {
            const response = await fetch(`${API_BASE}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            await progressDone;          // let progress animation finish
            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const data = await response.json();
            
            if (data.error) throw new Error(data.error);
            showVerdict(data);

        } catch (err) {
            updateProgress(100, '⚠ ' + err.message);
            setTimeout(() => resetUI(), 3000);
        }
    });

    resetBtn.addEventListener('click', resetUI);

    // ── Progress helpers ─────────────────────────────────
    function showProgress() {
        inputSection.classList.add('hidden');
        verdictSection.classList.add('hidden');
        progressSection.classList.remove('hidden');
        updateProgress(5, 'Initializing pipeline…');
    }

    function updateProgress(pct, msg) {
        progressBar.style.width = pct + '%';
        statusMessage.textContent = msg;

        // Highlight active progress step
        const steps = document.querySelectorAll('.progress-steps .step');
        steps.forEach((s, i) => {
            const thresholds = [20, 50, 75, 95];
            s.classList.toggle('active', pct >= thresholds[i]);
        });
    }

    async function simulateProgress(mode) {
        const stages = mode === 'image' ? [
            { p: 15,  m: 'Extracting text and details from image…' },
            { p: 35,  m: 'Searching for evidence across sources…' },
            { p: 68,  m: 'Classifying stance with BERT/MNLI…' },
            { p: 88,  m: 'Computing weighted verdict score…' },
            { p: 97,  m: 'Generating explanation via LLM…' },
        ] : [
            { p: 18,  m: 'Searching for evidence across sources…' },
            { p: 42,  m: 'Reading and extracting article snippets…' },
            { p: 68,  m: 'Classifying stance with BERT/MNLI…' },
            { p: 88,  m: 'Computing weighted verdict score…' },
            { p: 97,  m: 'Generating explanation via LLM…' },
        ];
        for (const s of stages) {
            updateProgress(s.p, s.m);
            await sleep(820);
        }
    }

    // ── Verdict display ──────────────────────────────────
    function showVerdict(data) {
        progressSection.classList.add('hidden');
        verdictSection.classList.remove('hidden');

        // Badge
        const v = (data.verdict || 'UNVERIFIED').toUpperCase();
        verdictBadge.textContent = data.localized_verdict ? data.localized_verdict.toUpperCase() : v;
        verdictBadge.className   = 'badge verdict-' + v.toLowerCase();

        // Confidence ring
        const pct    = Math.min(Math.max(data.confidence || 0, 0), 1);
        const offset = RING_CIRCUMFERENCE * (1 - pct);
        confidenceValue.textContent = Math.round(pct * 100) + '%';
        // small delay so CSS transition plays
        setTimeout(() => { ringFill.style.strokeDashoffset = offset; }, 60);

        // Explanation
        explanation.textContent = data.explanation || '—';

        // Sub-claims (compound)
        renderSubclaims(data);

        // Sources
        renderSources(data.sources || []);
    }

    // ── Subclaims card ───────────────────────────────────
    const VERDICT_COLORS = {
        TRUE:        { bg: 'rgba(16,185,129,0.12)',  text: '#34d399', borderColor: '#10b981' },
        FALSE:       { bg: 'rgba(239,68,68,0.12)',   text: '#f87171', borderColor: '#ef4444' },
        MISLEADING:  { bg: 'rgba(245,158,11,0.12)',  text: '#fbbf24', borderColor: '#f59e0b' },
        CONFLICTING: { bg: 'rgba(99,102,241,0.12)',  text: '#818cf8', borderColor: '#6366f1' },
        UNVERIFIED:  { bg: 'rgba(107,114,128,0.10)', text: '#9ca3af', borderColor: '#6b7280' },
    };

    function renderSubclaims(data) {
        subclaimsCont.innerHTML = '';
        if (!data.is_compound || !data.sub_claims || !data.sub_claims.length) return;

        const wrap = document.createElement('div');
        wrap.className = 'card';
        wrap.style.marginBottom = '10px';

        const heading = document.createElement('div');
        heading.className = 'card-label';
        heading.innerHTML = `
            <svg viewBox="0 0 20 20" fill="currentColor">
              <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z"/>
            </svg>
            Claim Breakdown`;
        wrap.appendChild(heading);

        data.sub_claims.forEach((sc, idx) => {
            const vc       = VERDICT_COLORS[sc.verdict] || VERDICT_COLORS.UNVERIFIED;
            const confPct  = Math.round((sc.confidence || 0) * 100);

            const row = document.createElement('div');
            row.style.cssText = [
                'display:flex', 'align-items:flex-start', 'gap:8px',
                'padding:8px 10px', 'border-radius:8px', 'margin-bottom:5px',
                `background:${vc.bg}`, `border:1px solid ${vc.borderColor}30`,
            ].join(';');
            if (idx === data.sub_claims.length - 1) row.style.marginBottom = '0';

            const badge = document.createElement('span');
            badge.textContent = sc.localized_verdict ? sc.localized_verdict : sc.verdict;
            badge.style.cssText = [
                `color:${vc.text}`, 'font-size:9px', 'font-weight:700',
                'letter-spacing:0.5px',
                'white-space:nowrap', 'padding:2px 6px',
                `border-radius:4px`, `background:${vc.text}18`,
                'flex-shrink:0', 'margin-top:1px',
            ].join(';');

            const textEl = document.createElement('span');
            textEl.style.cssText = 'font-size:12px;color:#e8eaf0;flex:1;line-height:1.5;';
            textEl.textContent = sc.text;

            const conf = document.createElement('span');
            conf.textContent = confPct + '%';
            conf.style.cssText = [
                `color:${vc.text}`, 'font-size:11px', 'font-weight:700',
                'white-space:nowrap', 'flex-shrink:0', 'margin-top:1px',
            ].join(';');

            row.appendChild(badge);
            row.appendChild(textEl);
            row.appendChild(conf);
            wrap.appendChild(row);
        });

        subclaimsCont.appendChild(wrap);
    }

    // ── Sources list ─────────────────────────────────────
    const STANCE_CLASS = {
        SUPPORTING:    'stance-supporting',
        CONTRADICTING: 'stance-contradicting',
        NEUTRAL:       'stance-neutral',
    };

    function renderSources(sources) {
        sourcesList.innerHTML = '';
        if (!sources.length) {
            const li = document.createElement('li');
            li.style.color = 'var(--text-dim)';
            li.textContent = 'No sources found.';
            sourcesList.appendChild(li);
            return;
        }

        sources.forEach(src => {
            const name     = src.source || src.title || 'Source';
            const credLbl  = credLabel(src.credibility);
            const stanceCls= STANCE_CLASS[src.stance] || 'stance-neutral';
            const stanceTxt= (src.stance || 'NEUTRAL').charAt(0) +
                             (src.stance || 'NEUTRAL').slice(1).toLowerCase();

            const li = document.createElement('li');

            const link = document.createElement('span');
            link.className   = 'source-link';
            link.textContent = name;
            link.title       = src.url || '';
            link.addEventListener('click', (e) => {
                e.preventDefault();
                if (src.url) chrome.tabs.create({ url: src.url });
            });

            const meta = document.createElement('span');
            meta.className   = 'source-meta';
            meta.textContent = ` · ${credLbl}`;

            const pill = document.createElement('span');
            pill.className   = 'stance-pill ' + stanceCls;
            pill.textContent = stanceTxt;

            li.appendChild(link);
            li.appendChild(meta);
            li.appendChild(pill);
            sourcesList.appendChild(li);
        });
    }

    function credLabel(c) {
        if (c >= 0.85) return '★ High';
        if (c >= 0.65) return '◆ Med';
        return '◇ Low';
    }

    // ── Reset ─────────────────────────────────────────────
    function resetUI() {
        verdictSection.classList.add('hidden');
        progressSection.classList.add('hidden');
        inputSection.classList.remove('hidden');
        claimInput.value = '';
        charCount.textContent = '0';
        
        // Reset image
        currentImageBase64 = null;
        currentImageUrl = null;
        imagePreview.src = '';
        imagePreview.classList.add('hidden');
        imagePlaceholder.classList.remove('hidden');
        imageFileInput.value = '';

        progressBar.style.width = '0%';
        ringFill.style.strokeDashoffset = RING_CIRCUMFERENCE;
        statusMessage.textContent = 'Initializing…';
        document.querySelectorAll('.progress-steps .step')
                .forEach(s => s.classList.remove('active'));
    }

    // ── Helpers ──────────────────────────────────────────
    function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

    function injectSvgGradient() {
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', '0');
        svg.setAttribute('height', '0');
        svg.style.position = 'absolute';
        svg.innerHTML = `
          <defs>
            <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stop-color="#6366f1"/>
              <stop offset="100%" stop-color="#8b5cf6"/>
            </linearGradient>
          </defs>`;
        document.body.prepend(svg);
    }
});
