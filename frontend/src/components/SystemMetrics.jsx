import React, { useState, useEffect, useCallback } from 'react';

const BACKEND_URL = 'http://localhost:8000';

function BarRow({ label, pct, color, right }) {
  return (
    <div className="bar-row" style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
      <div style={{ width:160, fontSize:13, color:'var(--gray-600)', fontWeight:500, flexShrink:0 }}>{label}</div>
      <div style={{ flex:1, height:8, background:'var(--gray-100)', borderRadius:4, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${pct}%`, background:color, borderRadius:4 }} />
      </div>
      <div style={{ width:52, textAlign:'right', fontFamily:"'DM Mono',monospace", fontSize:13, fontWeight:500, color:'var(--gray-700)' }}>{right}</div>
    </div>
  );
}

export function SystemMetrics() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const r = await fetch(`${BACKEND_URL}/v1/metrics`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setMetrics(await r.json());
    } catch (e) {
      setError('Could not load metrics: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const dist     = metrics?.verdict_distribution || {};
  const total    = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
  const breakers = metrics?.circuit_breakers || {};

  const verdictColors = {
    TRUE: 'var(--green)', FALSE: 'var(--red)',
    MISLEADING: 'var(--amber)', CONFLICTING: 'var(--orange)', UNVERIFIED: 'var(--slate)',
  };

  return (
    <div id="metricsView">
      <div className="search-heading" style={{ marginBottom:'0.25rem', display:'flex', alignItems:'center', gap:12 }}>
        System Metrics
        <button onClick={load} disabled={loading} style={{ fontSize:12, padding:'4px 12px', border:'1px solid var(--gray-200)', borderRadius:6, background:'var(--white)', cursor:'pointer', color:'var(--gray-600)' }}>
          {loading ? '…' : '↻ Refresh'}
        </button>
      </div>
      <div className="search-sub" style={{ marginBottom:'1.5rem' }}>
        Real-time performance telemetry for the OSINT verification pipeline.
        <span style={{ fontFamily:"'DM Mono',monospace", fontSize:11, marginLeft:8, color: loading ? 'var(--amber)' : error ? 'var(--red)' : 'var(--green)' }}>
          {loading ? '● Loading' : error ? '● Error' : '● Live'}
        </span>
      </div>

      {error && (
        <div style={{ background:'#fff5f5', border:'1px solid var(--red-border)', borderRadius:8, padding:'10px 14px', fontSize:13, color:'var(--red)', marginBottom:'1.25rem' }}>
          ⚠️ {error}
        </div>
      )}

      {/* KPI cards */}
      <div className="metric-grid" style={{ gridTemplateColumns:'repeat(4,1fr)', marginBottom:'1.25rem' }}>
        {[
          { label:'Total Reports', value: metrics?.total_reports ?? '—',                                                        sub:'All-time verifications' },
          { label:'Redis Cache',   value: metrics == null ? '—' : metrics.redis_connected ? '✅ Online' : '❌ Offline',          sub:'Result caching layer'  },
          { label:'Database',      value: metrics == null ? '—' : metrics.db_connected    ? '✅ Online' : '❌ Offline',          sub:'PostgreSQL connection'  },
          { label:'Offline Mode',  value: metrics == null ? '—' : metrics.offline_mode    ? '⚠️ Yes'    : '✅ No',              sub:'API-less fallback mode' },
        ].map(m => (
          <div key={m.label} className="metric-card" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'14px 12px', textAlign:'center' }}>
            <span className="metric-value" style={{ fontSize:18 }}>{String(m.value)}</span>
            <div className="metric-label">{m.label}</div>
            <div style={{ fontSize:10, color:'var(--gray-400)', marginTop:4 }}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Verdict Distribution */}
      <div className="trace-section" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'1.25rem', marginBottom:'1.25rem' }}>
        <div className="section-title" style={{ fontSize:11, fontWeight:600, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--gray-400)', marginBottom:14 }}>
          Verdict Distribution
        </div>
        {loading && <div style={{ fontSize:12, color:'var(--gray-400)' }}>Loading…</div>}
        {!loading && !Object.keys(dist).length && <div style={{ fontSize:12, color:'var(--gray-400)' }}>No reports in DB yet.</div>}
        {Object.entries(dist).map(([verdict, count]) => {
          const pct   = Math.round((count / total) * 100);
          const color = verdictColors[verdict] || 'var(--accent)';
          return <BarRow key={verdict} label={verdict} pct={pct} color={color} right={String(count)} />;
        })}
      </div>

      {/* Circuit Breakers */}
      <div className="trace-section" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'1.25rem', marginBottom:'1.25rem' }}>
        <div className="section-title" style={{ fontSize:11, fontWeight:600, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--gray-400)', marginBottom:14 }}>
          Circuit Breaker Status
        </div>
        {loading && <div style={{ fontSize:12, color:'var(--gray-400)' }}>Loading…</div>}
        {!loading && !Object.keys(breakers).length && <div style={{ fontSize:12, color:'var(--gray-400)' }}>No circuit breaker data returned by backend.</div>}
        <div className="trace-grid">
          {Object.entries(breakers).map(([name, state]) => {
            const isOpen = state === 'OPEN' || state === true || (typeof state === 'object' && state?.state === 'OPEN');
            const label  = typeof state === 'string' ? state : (isOpen ? 'OPEN' : 'CLOSED');
            const errCnt = typeof state === 'object' ? (state?.failures ?? '') : '';
            return (
              <div key={name} className="trace-item">
                <div className="trace-key">{name}</div>
                <div className="trace-value trace-flag">
                  <div className={`flag-dot ${isOpen ? 'flag-on' : 'flag-off'}`} />
                  {label}{errCnt ? ` ×${errCnt}` : ''}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {metrics?.version && (
        <div style={{ fontSize:12, color:'var(--gray-400)', textAlign:'center', marginTop:8 }}>
          Backend v{metrics.version} · Data from GET /v1/metrics
        </div>
      )}
    </div>
  );
}