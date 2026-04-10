import React, { useState, useCallback, useEffect, useRef } from 'react';
import { MetricsBar } from './components/MetricsBar.jsx';
import { VerdictCard } from './components/VerdictCard.jsx';
import { ProgressBar } from './components/ProgressBar.jsx';
import { History } from './components/History.jsx';
import { SystemMetrics } from './components/SystemMetrics.jsx';
import { MutationChains } from './components/MutationChains.jsx';
import { SourceCredibility } from './components/SourceCredibility.jsx';
import SourceCard from './components/SourceCard.jsx';
import './style.css';

const BACKEND_URL = 'http://localhost:8000';

const SIDEBAR_NAV = [
  { id: 'verify',             icon: '🔍', label: 'Verify Claim'       },
  { id: 'dashboard',          icon: '📊', label: 'Dashboard'          },
  { id: 'metrics',            icon: '📈', label: 'System Metrics'     },
  { id: 'mutation-chains',    icon: '🔀', label: 'Mutation Chains'    },
  { id: 'source-credibility', icon: '🌐', label: 'Source Credibility' },
];

// ── Static dashboard (own component — avoids stale-closure issues) ────────
function DashboardView() {
  return (
    <div id="dashboardView">
      <div className="search-heading" style={{ marginBottom: '1.5rem' }}>System Dashboard</div>
      <div className="metric-grid" style={{ marginBottom: '1.5rem' }}>
        {[
          { value: '868',  label: 'Total Claims'    },
          { value: '81%',  label: 'Avg Confidence'  },
          { value: '67%',  label: 'Cache Hit Rate'  },
          { value: '43%',  label: 'Early Exit Rate' },
          { value: '5.8s', label: 'Avg Processing'  },
          { value: '71%',  label: 'Ollama Usage'    },
        ].map(m => (
          <div key={m.label} className="metric-card">
            <span className="metric-value">{m.value}</span>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      <div style={{ background: 'var(--white)', border: '1px solid var(--gray-100)', borderRadius: 12, padding: '1.25rem', marginBottom: '1.25rem' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gray-400)', marginBottom: 12 }}>Verdict Distribution</div>
        {[
          { label: 'TRUE',        pct: 16, count: 142, color: 'var(--green)'  },
          { label: 'FALSE',       pct: 45, count: 389, color: 'var(--red)'    },
          { label: 'MISLEADING',  pct: 23, count: 201, color: 'var(--amber)'  },
          { label: 'CONFLICTING', pct: 5,  count: 47,  color: 'var(--orange)' },
          { label: 'UNVERIFIED',  pct: 10, count: 89,  color: 'var(--slate)'  },
        ].map(v => (
          <div key={v.label} className="bar-row">
            <div className="bar-label" style={{ width: 90, fontSize: 13, color: 'var(--gray-600)', fontWeight: 500 }}>{v.label}</div>
            <div className="bar-track" style={{ flex: 1, height: 10, background: 'var(--gray-100)', borderRadius: 5, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${v.pct}%`, background: v.color, borderRadius: 5 }} />
            </div>
            <div style={{ width: 44, textAlign: 'right', fontFamily: "'DM Mono',monospace", fontSize: 13, fontWeight: 500 }}>{v.count}</div>
          </div>
        ))}
      </div>

      <div className="trace-section">
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gray-400)', marginBottom: 12 }}>LLM Provider Usage</div>
        <div className="trace-grid">
          {[['Ollama (Primary)', '71%'], ['Gemini Flash', '18%'], ['Groq Llama', '8%'], ['Rule-Based', '3%']].map(([k, v]) => (
            <div key={k} className="trace-item">
              <div className="trace-key">{k}</div>
              <div className="trace-value">{v}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="trace-section" style={{ marginTop: '1.25rem' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gray-400)', marginBottom: 12 }}>Circuit Breaker Status</div>
        <div className="trace-grid">
          {[['NewsAPI', false], ['Snopes', true], ['SERP', false], ['GDELT', false]].map(([name, open]) => (
            <div key={name} className="trace-item">
              <div className="trace-key">{name}</div>
              <div className="trace-value trace-flag">
                <div className={`flag-dot ${open ? 'flag-on' : 'flag-off'}`} />
                {open ? 'OPEN ×1' : 'CLOSED'}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────
function App() {
  const [currentView,    setCurrentView]    = useState('verify');
  const [currentProfile, setCurrentProfile] = useState('general');
  const [selectedType,   setSelectedType]   = useState('auto');
  const [currentReport,  setCurrentReport]  = useState(null);
  const [loading,        setLoading]        = useState(false);
  const [historyTrigger, setHistoryTrigger] = useState(0);
  // lastResult is passed directly to History so it can add the entry
  // immediately without waiting for the backend
  const [lastResult,     setLastResult]     = useState(null);
  const [claimText,      setClaimText]      = useState('');

  const verifyBtnRef  = useRef(null);
  const claimInputRef = useRef(null);

  const profiles = ['general', 'journalist', 'researcher'];

  const cycleProfile = useCallback(() => {
    const idx = profiles.indexOf(currentProfile);
    setCurrentProfile(profiles[(idx + 1) % profiles.length]);
  }, [currentProfile]);

  const autoResize = useCallback((ta) => {
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  }, []);

  const startVerification = useCallback(async () => {
    const text = claimText.trim();
    if (!text) return;

    setLoading(true);
    setCurrentReport(null);

    try {
      const response = await fetch(`${BACKEND_URL}/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          claim: text,
          claim_type: selectedType === 'auto' ? 'general' : selectedType,
        }),
      });

      if (!response.ok) throw new Error(`Backend error: ${response.status}`);

      const report = await response.json();
      setCurrentReport(report);

      // ── KEY FIX: push result directly into History via props ──
      // This stores to localStorage immediately — no backend dependency.
      setLastResult(report);
      setHistoryTrigger(prev => prev + 1);

    } catch (error) {
      console.error('Verification failed:', error);
      alert(`Verification failed: ${error.message}.\nEnsure the backend is running at ${BACKEND_URL}`);
      setCurrentReport(null);
    } finally {
      setLoading(false);
    }
  }, [claimText, selectedType]);

  const handleClaimChange = useCallback((e) => {
    setClaimText(e.target.value);
    autoResize(e.target);
  }, [autoResize]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      startVerification();
    }
  }, [startVerification]);

  useEffect(() => {
    const input = claimInputRef.current;
    if (input) {
      input.addEventListener('keydown', handleKeyDown);
      return () => input.removeEventListener('keydown', handleKeyDown);
    }
  }, [handleKeyDown]);

  // ── Verify view (render function — reads latest state each render) ────
  const renderVerifyView = () => (
    <div id="verifyView">
      <div className="search-area">
        <div className="search-heading">Verify a Claim</div>
        <div className="search-sub">
          Enter any news claim, rumor, or statement to fact-check using OSINT sources.
        </div>

        <div className="search-box">
          <div className="search-input-wrap">
            <span className="search-icon">🔍</span>
            <textarea
              ref={claimInputRef}
              className="search-input"
              placeholder="e.g. Scientists have found a link between 5G towers and COVID-19 symptoms..."
              value={claimText}
              onChange={handleClaimChange}
              disabled={loading}
            />
          </div>
          <button
            ref={verifyBtnRef}
            className="search-btn"
            onClick={startVerification}
            disabled={loading || !claimText.trim()}
          >
            {loading ? 'Verifying...' : 'Verify →'}
          </button>
        </div>

        <div className="claim-type-row">
          {[
            { id: 'auto',          label: '🤖 Auto-detect'  },
            { id: 'breaking_news', label: '⚡ Breaking News' },
            { id: 'scientific',    label: '🔬 Scientific'   },
            { id: 'political',     label: '🏛️ Political'    },
            { id: 'general',       label: '📄 General'      },
          ].map(t => (
            <div
              key={t.id}
              className={`claim-type-tag ${selectedType === t.id ? 'selected' : ''}`}
              onClick={() => setSelectedType(t.id)}
            >
              {t.label}
            </div>
          ))}
        </div>
      </div>

      <ProgressBar loading={loading} />

      {currentReport && (
        <div className="killer-screen visible">
          <VerdictCard result={currentReport} claimText={claimText} />
        </div>
      )}

      {!loading && !currentReport && (
        <div className="empty-state">
          <div className="es-icon">🔍</div>
          <div className="es-title">Ready to verify</div>
          <div className="es-text">Enter a claim above and press Verify to begin OSINT analysis.</div>
        </div>
      )}
    </div>
  );

  // ── View router ───────────────────────────────────────
  const renderView = () => {
    switch (currentView) {
      case 'verify':             return renderVerifyView();
      case 'dashboard':          return <DashboardView />;
      case 'metrics':            return <SystemMetrics />;
      case 'mutation-chains':    return <MutationChains />;
      case 'source-credibility': return <SourceCredibility />;
      default:                   return renderVerifyView();
    }
  };

  return (
    <div className="app">
      <MetricsBar
        currentView={currentView}
        onViewChange={setCurrentView}
        currentProfile={currentProfile}
        onProfileChange={cycleProfile}
      />

      <div className="app-layout">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-section">
            <div className="sidebar-label">Navigation</div>
            {SIDEBAR_NAV.map(item => (
              <div
                key={item.id}
                className={`sidebar-item ${currentView === item.id ? 'active' : ''}`}
                onClick={() => setCurrentView(item.id)}
              >
                <span className="icon">{item.icon}</span>
                {item.label}
              </div>
            ))}
          </div>

          {/* Pass lastResult so History can add entries without backend */}
          <History
            refreshTrigger={historyTrigger}
            lastResult={lastResult}
          />
        </aside>

        {/* Main */}
        <main className="main-content">
          {renderView()}
        </main>

        {/* Right panel */}
        <aside className="right-panel">
          <div className="section-title" style={{ marginBottom: 12 }}>Platform Info</div>
          <div className="trace-grid" style={{ marginBottom: '1rem' }}>
            {[['Version', 'v5.2.0'], ['LLM', 'Ollama'], ['Model', 'Qwen2.5 3B'], ['GPU', 'RTX 4050']].map(([k, v]) => (
              <div key={k} className="trace-item">
                <div className="trace-key">{k}</div>
                <div className="trace-value">{v}</div>
              </div>
            ))}
          </div>
          <div className="section-title" style={{ marginBottom: 10 }}>Cache Status</div>
          <div className="trace-grid">
            {[
              ['Claims (24h)',      '✅ Active'],
              ['Embeddings (12h)', '✅ Active'],
              ['LLM Cache (6h)',   '✅ Active'],
              ['Cred (7d)',        '✅ Active'],
            ].map(([k, v]) => (
              <div key={k} className="trace-item">
                <div className="trace-key">{k}</div>
                <div className="trace-value">{v}</div>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}

export default App;