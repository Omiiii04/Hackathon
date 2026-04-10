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


// ── Live Dashboard — fetches /v1/metrics + /history ───────────────────────

function DashboardView() {
  const [metrics,  setMetrics]  = useState(null);
  const [history,  setHistory]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [mRes, hRes] = await Promise.all([
        fetch(`${BACKEND_URL}/v1/metrics`, { signal: AbortSignal.timeout(8000) }),
        fetch(`${BACKEND_URL}/history`,    { signal: AbortSignal.timeout(6000) }),
      ]);
      if (mRes.ok) setMetrics(await mRes.json());
      if (hRes.ok) { const d = await hRes.json(); setHistory(d.history || []); }
      if (!mRes.ok && !hRes.ok) setError('Backend unreachable — start with: uvicorn main:app --reload --port 8000');
    } catch (e) {
      setError('Could not reach backend: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const verdictColors = {
    TRUE: 'var(--green)', FALSE: 'var(--red)',
    MISLEADING: 'var(--amber)', CONFLICTING: 'var(--orange)', UNVERIFIED: 'var(--slate)',
  };

  const dist  = metrics?.verdict_distribution || {};
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
  const breakers = metrics?.circuit_breakers || {};

  return (
    <div id="dashboardView">
      <div className="search-heading" style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: 12 }}>
        System Dashboard
        <button onClick={load} disabled={loading} style={{ fontSize: 12, padding: '4px 12px', border: '1px solid var(--gray-200)', borderRadius: 6, background: 'var(--white)', cursor: 'pointer', color: 'var(--gray-600)' }}>
          {loading ? '…' : '↻ Refresh'}
        </button>
      </div>

      {error && (
        <div style={{ background: '#fff5f5', border: '1px solid var(--red-border)', borderRadius: 8, padding: '10px 14px', fontSize: 13, color: 'var(--red)', marginBottom: '1.25rem' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Live metric cards */}
      <div className="metric-grid" style={{ marginBottom: '1.5rem' }}>
        {[
          { label: 'Total Reports', value: metrics?.total_reports ?? '—' },
          { label: 'Redis Cache',   value: metrics == null ? '—' : metrics.redis_connected ? '✅ Online' : '❌ Offline' },
          { label: 'Database',      value: metrics == null ? '—' : metrics.db_connected    ? '✅ Online' : '❌ Offline' },
          { label: 'API Version',   value: metrics?.version ?? '—' },
          { label: 'Offline Mode',  value: metrics == null ? '—' : metrics.offline_mode ? 'Yes' : 'No' },
        ].map(m => (
          <div key={m.label} className="metric-card">
            <span className="metric-value" style={{ fontSize: 18 }}>{String(m.value)}</span>
            <div className="metric-label">{m.label}</div>
          </div>
        ))}
      </div>

      {/* Verdict distribution */}
      <div style={{ background: 'var(--white)', border: '1px solid var(--gray-100)', borderRadius: 12, padding: '1.25rem', marginBottom: '1.25rem' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gray-400)', marginBottom: 12 }}>Verdict Distribution</div>
        {loading && <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>Loading…</div>}
        {!loading && !Object.keys(dist).length && <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>No reports yet.</div>}
        {Object.entries(dist).map(([verdict, count]) => {
          const pct   = Math.round((count / total) * 100);
          const color = verdictColors[verdict] || 'var(--accent)';
          return (
            <div key={verdict} className="bar-row">
              <div className="bar-label" style={{ width: 90, fontSize: 13, color: 'var(--gray-600)', fontWeight: 500 }}>{verdict.slice(0, 9)}</div>
              <div className="bar-track" style={{ flex: 1, height: 10, background: 'var(--gray-100)', borderRadius: 5, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 5 }} />
              </div>
              <div style={{ width: 44, textAlign: 'right', fontFamily: "'DM Mono',monospace", fontSize: 13, fontWeight: 500 }}>{count}</div>
            </div>
          );
        })}
      </div>

      {/* Circuit breakers */}
      <div className="trace-section" style={{ marginBottom: '1.25rem' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gray-400)', marginBottom: 12 }}>Circuit Breaker Status</div>
        <div className="trace-grid">
          {loading && <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>Loading…</div>}
          {!loading && !Object.keys(breakers).length && <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>No circuit breaker data.</div>}
          {Object.entries(breakers).map(([name, state]) => {
            const isOpen = state === 'OPEN' || state === true || (typeof state === 'object' && state?.state === 'OPEN');
            const label  = typeof state === 'string' ? state : (isOpen ? 'OPEN' : 'CLOSED');
            return (
              <div key={name} className="trace-item">
                <div className="trace-key">{name}</div>
                <div className="trace-value trace-flag">
                  <div className={`flag-dot ${isOpen ? 'flag-on' : 'flag-off'}`} />
                  {label}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Recent history table */}
      <div style={{ background: 'var(--white)', border: '1px solid var(--gray-100)', borderRadius: 12, padding: '1.25rem' }}>
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gray-400)', marginBottom: 12 }}>Recent Verification History</div>
        {loading && <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>Loading…</div>}
        {!loading && !history.length && <div style={{ fontSize: 12, color: 'var(--gray-400)' }}>No verifications yet.</div>}
        {history.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--gray-100)' }}>
                {['Claim', 'Verdict', 'Time'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '8px 6px', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--gray-400)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 10).map((row, i) => {
                const v     = (row.verdict || 'UNVERIFIED').toUpperCase();
                const color = verdictColors[v] || 'var(--slate)';
                return (
                  <tr key={i} style={{ borderBottom: '1px solid var(--gray-50)' }}>
                    <td style={{ padding: '8px 6px', color: 'var(--gray-800)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{(row.claim || '').slice(0, 80)}</td>
                    <td style={{ padding: '8px 6px', fontWeight: 700, color }}>{v}</td>
                    <td style={{ padding: '8px 6px', color: 'var(--gray-400)', fontSize: 12, whiteSpace: 'nowrap' }}>{row.timestamp || ''}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
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