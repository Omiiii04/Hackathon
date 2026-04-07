/* ═══════════════════════════════════════════════════════
   OSINT Rumor Verification Platform — app.js
   SRS v5.2.0 · Team Radio Frequency · VIT Code Apex 2.0
   ═══════════════════════════════════════════════════════ */

/* ─────────────────────────────────────────── */
/*  STATE                                      */
/* ─────────────────────────────────────────── */
let currentProfile = 'general';
let selectedType   = 'auto';
let activeTab      = 'overview';
let currentReport  = null;

const profiles      = ['general', 'journalist', 'researcher'];
const profileLabels = { general: 'General', journalist: 'Journalist', researcher: 'Researcher' };

/* ─────────────────────────────────────────── */
/*  DEMO DATA                                  */
/* ─────────────────────────────────────────── */
const demoReports = {
  FALSE: {
    verdict: 'FALSE',
    confidence: 0.84,
    claim_type: 'scientific',
    claim_text: '5G towers cause COVID-19 symptoms',
    explanation:
      'Multiple Tier-1 scientific institutions including WHO and CDC have found no causal link between 5G radio frequencies and COVID-19 or its symptoms. The coronavirus is a biological pathogen transmitted person-to-person; electromagnetic waves cannot cause viral infections.',
    llm_provider: 'ollama',
    processing_ms: 5840,
    cached: false,
    early_exit: true,
    support_bar: { support_pct: 8, contradict_pct: 92 },
    is_mutation: true,
    mutation_similarity: 0.82,
    mutation_original: 'Radiation from cell towers causes flu-like illness',
    adversarial: true,
    adversarial_signal: 'COORDINATED_SOURCE_SPAM: 4 low-credibility sources published within 1h',
    verdict_tags: ['Low credibility sources', 'Early exit triggered', 'Echo chamber detected'],
    sources: [
      { name: 'WHO',         domain: 'who.int',         tier: 1, credibility: 0.97, stance: 'CONTRADICTING', date: 'Mar 2024', shift: +0.02 },
      { name: 'CDC',         domain: 'cdc.gov',         tier: 1, credibility: 0.96, stance: 'CONTRADICTING', date: 'Feb 2024', shift:  0    },
      { name: 'Reuters',     domain: 'reuters.com',     tier: 1, credibility: 0.93, stance: 'CONTRADICTING', date: 'Jan 2024', shift: +0.01 },
      { name: 'The Guardian',domain: 'guardian.com',    tier: 2, credibility: 0.82, stance: 'CONTRADICTING', date: 'Dec 2023', shift: -0.01 },
      { name: 'Unknown Blog',domain: 'healthtruth.net', tier: 4, credibility: 0.28, stance: 'SUPPORTING',    date: 'Jan 2024', shift: -0.03 },
    ],
    sub_claims: [
      { text: '5G towers emit harmful radiation',  verdict: 'FALSE' },
      { text: 'COVID-19 was man-made',             verdict: 'MISLEADING' },
      { text: 'Masks do not prevent viral spread', verdict: 'FALSE' },
    ],
    trace: {
      support_ratio:         0.087,
      total_evidence_items:  18,
      tier1_sources_found:   3,
      temporal_mismatch:     false,
      echo_chamber_penalty:  false,
      early_exit_triggered:  true,
      event_date:            '2024-01-10',
      utterance_date:        '2024-01-15',
      confidence_raw:        0.89,
      confidence_final:      0.84,
      claim_type:            'scientific',
      threshold_TRUE:        0.75,
      threshold_FALSE:       0.25,
    },
    evidence_graph: {
      nodes: [
        { id: 'who.int',         tier: 1, stance: 'CONTRADICTING', score: 0.91 },
        { id: 'cdc.gov',         tier: 1, stance: 'CONTRADICTING', score: 0.88 },
        { id: 'reuters.com',     tier: 1, stance: 'CONTRADICTING', score: 0.83 },
        { id: 'guardian.com',    tier: 2, stance: 'CONTRADICTING', score: 0.72 },
        { id: 'healthtruth.net', tier: 4, stance: 'SUPPORTING',    score: 0.21 },
      ],
      edges: [
        { source: 'who.int',     target: 'cdc.gov',      claim_overlap: 0.85 },
        { source: 'who.int',     target: 'reuters.com',  claim_overlap: 0.71 },
        { source: 'cdc.gov',     target: 'guardian.com', claim_overlap: 0.63 },
      ],
    },
    mutation_chain: [
      { text: 'Radiation from cell towers causes flu-like illness', similarity: 0.82, verdict: 'FALSE', date: '2020-04-10' },
      { text: 'WiFi signals weaken immune system',                  similarity: 0.76, verdict: 'FALSE', date: '2020-02-03' },
    ],
  },

  TRUE: {
    verdict: 'TRUE',
    confidence: 0.91,
    claim_type: 'breaking_news',
    claim_text: 'WHO declared mpox a global health emergency',
    explanation:
      'The World Health Organization officially declared mpox (formerly monkeypox) a Public Health Emergency of International Concern in August 2024, citing accelerating spread across multiple continents. This declaration was confirmed by multiple Tier-1 sources including Reuters, AP News, and BBC.',
    llm_provider: 'ollama',
    processing_ms: 4200,
    cached: true,
    early_exit: false,
    support_bar: { support_pct: 94, contradict_pct: 6 },
    is_mutation: false,
    adversarial: false,
    verdict_tags: ['3 Tier-1 sources', 'High confidence', 'Multiple corroborating sources'],
    sources: [
      { name: 'AP News', domain: 'apnews.com',    tier: 1, credibility: 0.95, stance: 'SUPPORTING', date: 'Aug 2024', shift: +0.01 },
      { name: 'BBC',     domain: 'bbc.com',        tier: 1, credibility: 0.94, stance: 'SUPPORTING', date: 'Aug 2024', shift:  0    },
      { name: 'Reuters', domain: 'reuters.com',    tier: 1, credibility: 0.93, stance: 'SUPPORTING', date: 'Aug 2024', shift: +0.02 },
      { name: 'NYT',     domain: 'nytimes.com',   tier: 2, credibility: 0.85, stance: 'SUPPORTING', date: 'Aug 2024', shift:  0    },
    ],
    sub_claims: [
      { text: 'WHO made an official declaration',            verdict: 'TRUE' },
      { text: 'Mpox spreads across multiple continents',     verdict: 'TRUE' },
      { text: 'Emergency protocols were activated',          verdict: 'TRUE' },
    ],
    trace: {
      support_ratio:         0.940,
      total_evidence_items:  12,
      tier1_sources_found:   3,
      temporal_mismatch:     false,
      echo_chamber_penalty:  false,
      early_exit_triggered:  false,
      event_date:            '2024-08-14',
      utterance_date:        '2024-08-15',
      confidence_raw:        0.94,
      confidence_final:      0.91,
      claim_type:            'breaking_news',
      threshold_TRUE:        0.70,
      threshold_FALSE:       0.30,
    },
    evidence_graph: {
      nodes: [
        { id: 'apnews.com',  tier: 1, stance: 'SUPPORTING', score: 0.93 },
        { id: 'bbc.com',     tier: 1, stance: 'SUPPORTING', score: 0.90 },
        { id: 'reuters.com', tier: 1, stance: 'SUPPORTING', score: 0.87 },
        { id: 'nytimes.com', tier: 2, stance: 'SUPPORTING', score: 0.79 },
      ],
      edges: [
        { source: 'apnews.com',  target: 'bbc.com',     claim_overlap: 0.80 },
        { source: 'apnews.com',  target: 'reuters.com', claim_overlap: 0.75 },
        { source: 'bbc.com',     target: 'nytimes.com', claim_overlap: 0.66 },
      ],
    },
    mutation_chain: [],
  },

  CONFLICTING: {
    verdict: 'CONFLICTING',
    confidence: 0.62,
    claim_type: 'scientific',
    claim_text: 'New study links coffee to longevity',
    explanation:
      'High-credibility scientific sources disagree on this claim. While several observational studies suggest moderate coffee consumption correlates with longevity markers, other peer-reviewed research highlights confounding variables and warns against establishing causality.',
    llm_provider: 'gemini',
    processing_ms: 7100,
    cached: false,
    early_exit: false,
    support_bar: { support_pct: 52, contradict_pct: 48 },
    is_mutation: false,
    adversarial: false,
    verdict_tags: ['Split evidence', 'Scientific claim', 'Peer-reviewed sources'],
    sources: [
      { name: 'NEJM',          domain: 'nejm.org',          tier: 1, credibility: 0.95, stance: 'SUPPORTING',    date: 'Nov 2023', shift:  0    },
      { name: 'The Lancet',    domain: 'thelancet.com',     tier: 1, credibility: 0.94, stance: 'CONTRADICTING', date: 'Oct 2023', shift: +0.01 },
      { name: 'Harvard Health',domain: 'health.harvard.edu',tier: 2, credibility: 0.88, stance: 'SUPPORTING',    date: 'Sep 2023', shift:  0    },
      { name: 'BMJ',           domain: 'bmj.com',           tier: 1, credibility: 0.93, stance: 'CONTRADICTING', date: 'Aug 2023', shift: -0.01 },
    ],
    sub_claims: [
      { text: 'Observational studies show correlation', verdict: 'TRUE' },
      { text: 'Causal link is established',            verdict: 'MISLEADING' },
      { text: 'Effect is universal across populations',verdict: 'CONFLICTING' },
    ],
    trace: {
      support_ratio:         0.520,
      total_evidence_items:  14,
      tier1_sources_found:   4,
      temporal_mismatch:     false,
      echo_chamber_penalty:  false,
      early_exit_triggered:  false,
      event_date:            '2023-11-01',
      utterance_date:        '2023-11-05',
      confidence_raw:        0.67,
      confidence_final:      0.62,
      claim_type:            'scientific',
      threshold_TRUE:        0.75,
      threshold_FALSE:       0.25,
    },
    evidence_graph: {
      nodes: [
        { id: 'nejm.org',          tier: 1, stance: 'SUPPORTING',    score: 0.88 },
        { id: 'thelancet.com',     tier: 1, stance: 'CONTRADICTING', score: 0.85 },
        { id: 'health.harvard.edu',tier: 2, stance: 'SUPPORTING',    score: 0.74 },
        { id: 'bmj.com',           tier: 1, stance: 'CONTRADICTING', score: 0.80 },
      ],
      edges: [
        { source: 'nejm.org',      target: 'thelancet.com', claim_overlap: 0.62 },
        { source: 'thelancet.com', target: 'bmj.com',       claim_overlap: 0.70 },
      ],
    },
    mutation_chain: [],
  },

  MISLEADING: {
    verdict: 'MISLEADING',
    confidence: 0.73,
    claim_type: 'political',
    claim_text: 'Government secretly tracking citizens via vaccine',
    explanation:
      'While governments have implemented COVID-19 vaccination tracking for public health purposes, the claim that this constitutes secret surveillance is misleading. No credible evidence supports microchip implantation or covert tracking technology in vaccines.',
    llm_provider: 'ollama',
    processing_ms: 6300,
    cached: false,
    early_exit: false,
    support_bar: { support_pct: 21, contradict_pct: 79 },
    is_mutation: true,
    mutation_similarity: 0.78,
    mutation_original: 'COVID vaccine has microchips',
    adversarial: false,
    verdict_tags: ['Temporal mismatch', 'Context missing', 'Mutation variant'],
    sources: [
      { name: 'Reuters', domain: 'reuters.com', tier: 1, credibility: 0.93, stance: 'CONTRADICTING', date: 'Jan 2024', shift:  0    },
      { name: 'AP News', domain: 'apnews.com',  tier: 1, credibility: 0.95, stance: 'CONTRADICTING', date: 'Dec 2023', shift: +0.01 },
      { name: 'Snopes',  domain: 'snopes.com',  tier: 2, credibility: 0.80, stance: 'CONTRADICTING', date: 'Nov 2023', shift:  0    },
    ],
    sub_claims: [
      { text: 'Governments track vaccination status',   verdict: 'TRUE'  },
      { text: 'Vaccines contain tracking microchips',   verdict: 'FALSE' },
      { text: 'Tracking is secret/covert',              verdict: 'FALSE' },
    ],
    trace: {
      support_ratio:         0.210,
      total_evidence_items:  9,
      tier1_sources_found:   2,
      temporal_mismatch:     true,
      echo_chamber_penalty:  false,
      early_exit_triggered:  false,
      event_date:            '2021-03-01',
      utterance_date:        '2024-01-10',
      confidence_raw:        0.78,
      confidence_final:      0.73,
      claim_type:            'political',
      threshold_TRUE:        0.75,
      threshold_FALSE:       0.25,
    },
    evidence_graph: {
      nodes: [
        { id: 'reuters.com', tier: 1, stance: 'CONTRADICTING', score: 0.85 },
        { id: 'apnews.com',  tier: 1, stance: 'CONTRADICTING', score: 0.82 },
        { id: 'snopes.com',  tier: 2, stance: 'CONTRADICTING', score: 0.67 },
      ],
      edges: [
        { source: 'reuters.com', target: 'apnews.com', claim_overlap: 0.73 },
      ],
    },
    mutation_chain: [
      { text: 'COVID vaccine has microchips', similarity: 0.78, verdict: 'FALSE', date: '2021-01-15' },
    ],
  },

  UNVERIFIED: {
    verdict: 'UNVERIFIED',
    confidence: 0.0,
    claim_type: 'breaking_news',
    claim_text: 'Parliament dissolves unexpectedly amid political crisis',
    explanation:
      'Insufficient credible coverage found at verification time. Only 1 source found, below the minimum threshold of 3 required for a definitive verdict. This breaking news story may develop further.',
    llm_provider: 'rule_based',
    processing_ms: 2100,
    cached: false,
    early_exit: false,
    support_bar: null,
    is_mutation: false,
    adversarial: false,
    verdict_tags: ['Insufficient sources', 'Breaking news', 'Check back later'],
    sources: [
      { name: 'Unknown Source', domain: 'localblog.net', tier: 4, credibility: 0.31, stance: 'SUPPORTING', date: 'Today', shift: 0 },
    ],
    sub_claims: [],
    trace: {
      support_ratio:         0,
      total_evidence_items:  0,
      tier1_sources_found:   0,
      temporal_mismatch:     false,
      echo_chamber_penalty:  false,
      early_exit_triggered:  false,
      event_date:            'today',
      utterance_date:        'today',
      confidence_raw:        0,
      confidence_final:      0,
      claim_type:            'breaking_news',
      threshold_TRUE:        0.70,
      threshold_FALSE:       0.30,
    },
    evidence_graph: { nodes: [], edges: [] },
    mutation_chain: [],
  },
};

/* ─────────────────────────────────────────── */
/*  VIEW SWITCHING                             */
/* ─────────────────────────────────────────── */
function switchView(view) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('verifyView').style.display    = 'none';
  document.getElementById('dashboardView').style.display = 'none';

  if (view === 'verify') {
    document.getElementById('verifyView').style.display = 'block';
    document.querySelectorAll('.nav-btn')[0].classList.add('active');
  } else if (view === 'dashboard') {
    document.getElementById('dashboardView').style.display = 'block';
    document.querySelectorAll('.nav-btn')[1].classList.add('active');
  }
}

/* ─────────────────────────────────────────── */
/*  PROFILE                                    */
/* ─────────────────────────────────────────── */
function cycleProfile() {
  const idx = profiles.indexOf(currentProfile);
  currentProfile = profiles[(idx + 1) % profiles.length];
  document.getElementById('profileLabel').textContent = profileLabels[currentProfile];
}

/* ─────────────────────────────────────────── */
/*  CLAIM TYPE                                 */
/* ─────────────────────────────────────────── */
function selectType(el, type) {
  document.querySelectorAll('.claim-type-tag').forEach(t => t.classList.remove('selected'));
  el.classList.add('selected');
  selectedType = type;
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = ta.scrollHeight + 'px';
}

/* ─────────────────────────────────────────── */
/*  TAB SWITCHING                              */
/* ─────────────────────────────────────────── */
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('[id^="tab-"]').forEach(t => (t.style.display = 'none'));

  const tabs = ['overview', 'sources', 'trace', 'subclaims'];
  const idx  = tabs.indexOf(tab);
  document.querySelectorAll('.tab-btn')[idx].classList.add('active');
  document.getElementById('tab-' + tab).style.display = 'block';
  activeTab = tab;
}

/* ─────────────────────────────────────────── */
/*  VERIFICATION SIMULATION                    */
/* ─────────────────────────────────────────── */
function startVerification() {
  const claimText = document.getElementById('claimInput').value.trim();
  if (!claimText) return;

  document.getElementById('verifyBtn').disabled = true;
  document.getElementById('killerScreen').classList.remove('visible');
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('progressSection').classList.add('visible');

  // Reset all dots
  ['parsing', 'searching', 'scoring', 'explaining', 'complete'].forEach(s => {
    const d = document.getElementById('dot-' + s);
    d.classList.remove('done', 'active');
  });

  const stages = [
    { stage: 'parsing',    progress: 15,  msg: 'Extracting entities & claim type…',  dot: 'parsing',    delay: 600  },
    { stage: 'searching',  progress: 35,  msg: 'Querying 10 sources in parallel…',   dot: 'searching',  delay: 1200 },
    { stage: 'searching',  progress: 55,  msg: 'Running BART-MNLI batched scoring…', dot: 'scoring',    delay: 1000 },
    { stage: 'explaining', progress: 80,  msg: 'Generating explanation (Ollama)…',   dot: 'explaining', delay: 1200 },
    { stage: 'complete',   progress: 100, msg: 'Verdict ready.',                      dot: 'complete',   delay: 600  },
  ];

  let elapsed = 0;
  stages.forEach((s, i) => {
    elapsed += s.delay;
    setTimeout(() => {
      document.getElementById('stageText').innerHTML =
        capitalise(s.stage) + '… <span>' + s.msg + '</span>';
      document.getElementById('progressFill').style.width = s.progress + '%';

      // Update dots
      if (i > 0) {
        const prevDot = document.getElementById('dot-' + stages[i - 1].dot);
        if (prevDot) { prevDot.classList.remove('active'); prevDot.classList.add('done'); }
      }
      const dot = document.getElementById('dot-' + s.dot);
      if (dot) dot.classList.add('active');

      if (s.stage === 'complete') {
        setTimeout(() => {
          dot.classList.remove('active');
          dot.classList.add('done');
          document.getElementById('progressSection').classList.remove('visible');
          document.getElementById('verifyBtn').disabled = false;

          // Pick demo verdict by keyword matching
          let pick = 'FALSE';
          const cl = claimText.toLowerCase();
          if (cl.includes('true') || cl.includes('who') || cl.includes('mpox'))              pick = 'TRUE';
          else if (cl.includes('conflict') || cl.includes('coffee') || cl.includes('study')) pick = 'CONFLICTING';
          else if (cl.includes('mislead') || cl.includes('vaccin') || cl.includes('track'))  pick = 'MISLEADING';
          else if (cl.includes('unverif') || cl.includes('breaking') || cl.includes('parliament')) pick = 'UNVERIFIED';

          renderReport(demoReports[pick], claimText);
        }, 400);
      }
    }, elapsed);
  });
}

function loadDemo(verdict) {
  switchView('verify');
  document.getElementById('emptyState').style.display = 'none';
  const report = demoReports[verdict];
  document.getElementById('claimInput').value = report.claim_text;
  autoResize(document.getElementById('claimInput'));
  renderReport(report, report.claim_text);
}

function capitalise(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/* ─────────────────────────────────────────── */
/*  RENDER REPORT                              */
/* ─────────────────────────────────────────── */
function renderReport(report, claimText) {
  currentReport = report;
  const v = report.verdict;

  // Verdict card
  const card = document.getElementById('verdictCard');
  card.className = 'verdict-card vc-' + v;

  const emojis = { TRUE: '✅', FALSE: '❌', MISLEADING: '⚠️', CONFLICTING: '🔀', UNVERIFIED: '❓' };
  document.getElementById('verdictEmoji').textContent = emojis[v];

  document.getElementById('verdictLabel').className   = 'verdict-label vl-' + v;
  document.getElementById('verdictLabel').textContent = v;
  document.getElementById('verdictClaim').textContent = '"' + claimText + '"';

  const ctIcons = { breaking_news: '⚡', scientific: '🔬', political: '🏛️', general: '📄' };
  document.getElementById('claimTypeBadge').innerHTML =
    (ctIcons[report.claim_type] || '📄') + ' ' + report.claim_type.replace('_', ' ');

  // Confidence ring
  const pct        = Math.round(report.confidence * 100);
  const circ       = 2 * Math.PI * 34;
  const offset     = circ * (1 - report.confidence);
  const confColors = {
    TRUE: '#16a34a', FALSE: '#dc2626', MISLEADING: '#d97706',
    CONFLICTING: '#ea580c', UNVERIFIED: '#6b7280',
  };
  document.getElementById('confRing').style.strokeDashoffset = offset;
  document.getElementById('confRing').setAttribute('stroke', confColors[v]);
  document.getElementById('confPct').textContent = pct + '%';

  document.getElementById('cachedBadge').style.display  = report.cached ? 'inline-flex' : 'none';
  document.getElementById('processingTime').textContent = report.processing_ms.toLocaleString() + 'ms';

  // Verdict tags
  const tagsHtml = (report.verdict_tags || []).map(t => `<span class="vtag">${t}</span>`).join('');
  document.getElementById('verdictTags').innerHTML = tagsHtml;

  // Mutation alert (journalist / researcher only)
  if (report.is_mutation && currentProfile !== 'general') {
    document.getElementById('mutationAlert').style.display = 'flex';
    document.getElementById('mutationAlert').querySelector('.mutation-alert-text').innerHTML =
      `<strong>Mutation Detected</strong>This is a variant of a known claim (similarity: ${report.mutation_similarity})`;
  } else {
    document.getElementById('mutationAlert').style.display = 'none';
  }

  // Adversarial warning
  if (report.adversarial) {
    document.getElementById('adversarialWarning').style.display = 'block';
    document.getElementById('adversarialWarning').innerHTML =
      `<strong>⚠️ Adversarial Signal Detected</strong>${report.adversarial_signal}`;
  } else {
    document.getElementById('adversarialWarning').style.display = 'none';
  }

  // Support bar
  renderSupportBar(report);

  // Explanation
  document.getElementById('explanationText').textContent = report.explanation;
  document.getElementById('llmProvider').textContent     = report.llm_provider;

  // Sources
  renderSources(report.sources || []);

  // Trace
  renderTrace(report.trace);

  // Sub-claims
  renderSubClaims(report.sub_claims || []);

  // Switch to overview tab
  switchTab('overview');

  // Show killer screen
  document.getElementById('killerScreen').classList.add('visible');
  document.getElementById('emptyState').style.display = 'none';

  // Right panel
  showRightPanel(report);
}

/* ─────────────────────────────────────────── */
/*  SUPPORT BAR                                */
/* ─────────────────────────────────────────── */
function renderSupportBar(report) {
  const container = document.getElementById('supportBarContent');

  // FR-157–160: UNVERIFIED + zero evidence → empty state bar
  if (report.verdict === 'UNVERIFIED' && (!report.support_bar || report.trace.total_evidence_items === 0)) {
    container.innerHTML = `
      <div class="bar-empty">
        <p>No evidence collected</p>
        <small>Sources may cover this later — check back</small>
      </div>`;
    return;
  }

  const sb = report.support_bar;
  container.innerHTML = `
    <div class="bar-row">
      <div class="bar-label">Support</div>
      <div class="bar-track">
        <div class="bar-fill bar-support" style="width:0%" data-pct="${sb.support_pct}"></div>
      </div>
      <div class="bar-pct">${sb.support_pct}%</div>
    </div>
    <div class="bar-row">
      <div class="bar-label">Contradict</div>
      <div class="bar-track">
        <div class="bar-fill bar-contradict" style="width:0%" data-pct="${sb.contradict_pct}"></div>
      </div>
      <div class="bar-pct">${sb.contradict_pct}%</div>
    </div>`;

  // Animate bars after paint
  setTimeout(() => {
    container.querySelectorAll('.bar-fill[data-pct]').forEach(el => {
      el.style.width = el.dataset.pct + '%';
    });
  }, 50);
}

/* ─────────────────────────────────────────── */
/*  SOURCES                                    */
/* ─────────────────────────────────────────── */
function renderSources(sources) {
  const maxSources = currentProfile === 'general' ? 3
    : currentProfile === 'journalist'              ? 10
    : sources.length;

  const shown = sources.slice(0, maxSources);
  const icons  = { 1: '🏛️', 2: '📰', 3: '📄', 4: '🌐', 5: '⚠️' };

  document.getElementById('sourcesContent').innerHTML = shown.map(s => `
    <div class="source-card">
      <div class="source-favicon">${icons[s.tier] || '🌐'}</div>
      <div class="source-info">
        <div class="source-name">${s.name}</div>
        <div class="source-meta">
          <span class="tier-badge t${s.tier}">T${s.tier}</span>
          <span class="source-date">${s.date}</span>
        </div>
        <div class="credibility-bar-mini">
          <div class="credibility-fill" style="width:${Math.round(s.credibility * 100)}%"></div>
        </div>
      </div>
      <div style="text-align:right;">
        <div class="source-stance ss-${s.stance}"></div>
        ${s.shift !== 0
          ? `<div class="credibility-shift ${s.shift > 0 ? 'shift-up' : 'shift-down'}">${s.shift > 0 ? '↑' : '↓'}${Math.abs(s.shift).toFixed(2)}</div>`
          : ''}
      </div>
    </div>`).join('');
}

/* ─────────────────────────────────────────── */
/*  ALGORITHM TRACE                            */
/* ─────────────────────────────────────────── */
function renderTrace(trace) {
  if (!trace) return;

  const items = [
    { key: 'Support Ratio', val: (trace.support_ratio * 100).toFixed(1) + '%' },
    { key: 'Evidence Items', val: trace.total_evidence_items },
    { key: 'Tier-1 Sources', val: trace.tier1_sources_found },
    { key: 'Claim Type',     val: trace.claim_type },
    { key: 'TRUE Threshold', val: (trace.threshold_TRUE  * 100).toFixed(0) + '%' },
    { key: 'FALSE Threshold',val: (trace.threshold_FALSE * 100).toFixed(0) + '%' },
    { key: 'Conf (raw)',     val: (trace.confidence_raw   * 100).toFixed(1) + '%' },
    { key: 'Conf (final)',   val: (trace.confidence_final * 100).toFixed(0) + '%' },
  ];

  const flags = [
    { key: 'Temporal Mismatch', val: trace.temporal_mismatch },
    { key: 'Echo Chamber',      val: trace.echo_chamber_penalty },
    { key: 'Early Exit',        val: trace.early_exit_triggered },
  ];

  document.getElementById('traceGrid').innerHTML =
    items.map(i => `
      <div class="trace-item">
        <div class="trace-key">${i.key}</div>
        <div class="trace-value">${i.val}</div>
      </div>`).join('') +
    flags.map(f => `
      <div class="trace-item">
        <div class="trace-key">${f.key}</div>
        <div class="trace-value trace-flag">
          <div class="flag-dot ${f.val ? 'flag-on' : 'flag-off'}"></div>
          ${f.val ? 'YES' : 'NO'}
        </div>
      </div>`).join('') + `
    <div class="trace-item">
      <div class="trace-key">Event Date</div>
      <div class="trace-value">${trace.event_date}</div>
    </div>
    <div class="trace-item">
      <div class="trace-key">Utterance Date</div>
      <div class="trace-value">${trace.utterance_date}</div>
    </div>`;
}

/* ─────────────────────────────────────────── */
/*  SUB-CLAIMS                                 */
/* ─────────────────────────────────────────── */
function renderSubClaims(subclaims) {
  const icons = { TRUE: '✅', FALSE: '❌', MISLEADING: '⚠️', CONFLICTING: '🔀', UNVERIFIED: '❓' };

  if (!subclaims.length) {
    document.getElementById('subclaimsContent').innerHTML =
      '<p style="font-size:13px;color:var(--gray-400);">No sub-claims extracted.</p>';
    return;
  }

  document.getElementById('subclaimsContent').innerHTML = subclaims.map(sc => `
    <div class="subclaim-row">
      <span class="subclaim-icon">${icons[sc.verdict]}</span>
      <span class="subclaim-text">${sc.text}</span>
      <span class="subclaim-badge v-${sc.verdict}">${sc.verdict}</span>
    </div>`).join('');
}

/* ─────────────────────────────────────────── */
/*  RIGHT PANEL                                */
/* ─────────────────────────────────────────── */
function showRightPanel(report) {
  document.getElementById('rightDefault').style.display = 'none';

  const showGraph = currentProfile !== 'general';
  document.getElementById('graphPanel').style.display    = showGraph ? 'block' : 'none';
  document.getElementById('timelinePanel').style.display = showGraph ? 'block' : 'none';

  if (showGraph) {
    drawGraph(report.evidence_graph);
    renderTimeline(report.sources || []);
  }

  const showMutation = report.is_mutation && currentProfile !== 'general';
  document.getElementById('mutationPanel').style.display = showMutation ? 'block' : 'none';
  if (showMutation) renderMutationChain(report.mutation_chain || []);

  document.getElementById('feedbackPanel').style.display = 'block';

  if (!showGraph && !showMutation) {
    document.getElementById('rightDefault').style.display = 'block';
  }
}

/* ─────────────────────────────────────────── */
/*  EVIDENCE GRAPH (Canvas)                    */
/* ─────────────────────────────────────────── */
function drawGraph(graphData) {
  const canvas    = document.getElementById('graphCanvas');
  const container = canvas.parentElement;
  canvas.width    = container.clientWidth;
  canvas.height   = container.clientHeight;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;

  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    ctx.fillStyle = '#9e9e9c';
    ctx.font      = '13px DM Sans';
    ctx.textAlign = 'center';
    ctx.fillText('No evidence graph available', W / 2, H / 2);
    return;
  }

  const nodes = graphData.nodes.map((n, i) => ({
    ...n,
    x: W / 2 + Math.cos((i / graphData.nodes.length) * 2 * Math.PI) * (W * 0.3),
    y: H / 2 + Math.sin((i / graphData.nodes.length) * 2 * Math.PI) * (H * 0.35),
  }));

  const nodeMap     = {};
  nodes.forEach(n => (nodeMap[n.id] = n));

  const stanceColors = {
    SUPPORTING:    '#16a34a',
    CONTRADICTING: '#dc2626',
    NEUTRAL:       '#9ca3af',
  };

  ctx.clearRect(0, 0, W, H);

  // Edges
  (graphData.edges || []).forEach(e => {
    const s = nodeMap[e.source], t = nodeMap[e.target];
    if (!s || !t) return;
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.strokeStyle = '#d1d5db';
    ctx.lineWidth   = e.claim_overlap * 3;
    ctx.stroke();
  });

  // Nodes
  nodes.forEach(n => {
    const r = 10 + (1 - (n.tier - 1) * 0.15) * 8;
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle   = stanceColors[n.stance] || '#9ca3af';
    ctx.fill();
    ctx.strokeStyle = 'white';
    ctx.lineWidth   = 2;
    ctx.stroke();

    // Label
    ctx.fillStyle = '#2a2a28';
    ctx.font      = '10px DM Mono';
    ctx.textAlign = 'center';
    const label   = n.id.replace('www.', '').split('.')[0];
    ctx.fillText(label, n.x, n.y + r + 13);
  });
}

/* ─────────────────────────────────────────── */
/*  SOURCE TIMELINE                            */
/* ─────────────────────────────────────────── */
function renderTimeline(sources) {
  const sorted       = [...sources].sort((a, b) => (a.date < b.date ? -1 : 1));
  const stanceColors = {
    SUPPORTING:    'var(--green)',
    CONTRADICTING: 'var(--red)',
    NEUTRAL:       'var(--gray-400)',
  };

  document.getElementById('timelineTrack').innerHTML = sorted.map(s => `
    <div class="timeline-node">
      <div class="timeline-dot" style="background:${stanceColors[s.stance] || 'var(--gray-400)'}"></div>
      <div class="timeline-name">${s.name}</div>
      <div class="timeline-meta">${s.date} · ${s.stance}</div>
    </div>`).join('');
}

/* ─────────────────────────────────────────── */
/*  MUTATION CHAIN                             */
/* ─────────────────────────────────────────── */
function renderMutationChain(chain) {
  if (!chain.length) {
    document.getElementById('mutationContent').innerHTML = '';
    return;
  }

  document.getElementById('mutationContent').innerHTML = chain.map(v => `
    <div class="mutation-variant">
      <div class="mutation-variant-text">"${v.text}"</div>
      <div class="mutation-sim">sim: ${v.similarity} · ${v.verdict} · ${v.date}</div>
    </div>`).join('');
}

/* ─────────────────────────────────────────── */
/*  FEEDBACK                                   */
/* ─────────────────────────────────────────── */
function submitFeedback(rating) {
  const panel = document.getElementById('feedbackPanel');
  panel.innerHTML = `
    <div class="section-title">Feedback submitted</div>
    <p style="font-size:13px;color:var(--gray-400);margin-top:6px;">
      ${rating === 'correct'
        ? '👍 Thanks! Credibility scores updated.'
        : "👎 Noted. We'll review this verdict."}
    </p>`;
}

/* ─────────────────────────────────────────── */
/*  INIT & KEYBOARD SHORTCUT                   */
/* ─────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('claimInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      startVerification();
    }
  });

  // Show empty state by default
  document.getElementById('emptyState').style.display = 'block';
});
