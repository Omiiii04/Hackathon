import React, { useState, useEffect, useCallback } from 'react';

const BACKEND_URL = 'http://localhost:8000';

const VERDICT_COLORS = {
  TRUE:        { bg:'#dcfce7', color:'#15803d' },
  FALSE:       { bg:'#fee2e2', color:'#b91c1c' },
  MISLEADING:  { bg:'#fef3c7', color:'#b45309' },
  UNVERIFIED:  { bg:'#f1f5f9', color:'#475569' },
  CONFLICTING: { bg:'#ffedd5', color:'#c2410c' },
};

function VerdictPill({ verdict }) {
  const s = VERDICT_COLORS[verdict] || VERDICT_COLORS.UNVERIFIED;
  return (
    <span style={{ display:'inline-block', fontSize:10, fontWeight:700, fontFamily:"'DM Mono',monospace",
      background:s.bg, color:s.color, borderRadius:4, padding:'2px 7px', letterSpacing:'0.05em' }}>
      {verdict}
    </span>
  );
}

function SimilarityBar({ value }) {
  const pct   = Math.round(value * 100);
  const color = pct >= 80 ? 'var(--red)' : pct >= 65 ? 'var(--amber)' : 'var(--green)';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6 }}>
      <div style={{ width:60, height:5, background:'var(--gray-200)', borderRadius:3, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${pct}%`, background:color, borderRadius:3 }} />
      </div>
      <span style={{ fontFamily:"'DM Mono',monospace", fontSize:11, color:'var(--gray-500)' }}>{value}</span>
    </div>
  );
}

/**
 * Build mutation chain groups from the raw /history items.
 * Each history item may include a `mutation_chain` array from the backend.
 * We surface those alongside any `is_mutation` items.
 */
function buildChains(historyItems) {
  const chains = [];
  for (const item of historyItems) {
    if (!item.claim) continue;
    const mc = item.mutation_chain || [];
    if (mc.length > 0 || item.is_mutation) {
      chains.push({
        original:    item.claim,
        verdict:     item.verdict || 'UNVERIFIED',
        confidence:  item.confidence ?? null,
        first_seen:  item.timestamp || '',
        variants:    mc.map(v => ({
          text:       v.text  || '',
          similarity: v.similarity ?? 0,
          verdict:    v.verdict    || 'UNVERIFIED',
          date:       v.date       || '',
        })),
      });
    }
  }
  return chains;
}

export function MutationChains() {
  const [chains,   setChains]   = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [expanded, setExpanded] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // Pull the full history — the backend returns `mutation_chain` per report
      const r = await fetch(`${BACKEND_URL}/v1/history?limit=50`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const built = buildChains(data.history || []);
      setChains(built);
      // Auto-expand the first entry
      if (built.length) setExpanded({ 0: true });
    } catch (e) {
      setError('Could not load mutation chains: ' + e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = (i) => setExpanded(prev => ({ ...prev, [i]: !prev[i] }));

  return (
    <div id="mutationChainsView">
      <div className="search-heading" style={{ marginBottom:'0.25rem', display:'flex', alignItems:'center', gap:12 }}>
        Mutation Chains
        <button onClick={load} disabled={loading} style={{ fontSize:12, padding:'4px 12px', border:'1px solid var(--gray-200)', borderRadius:6, background:'var(--white)', cursor:'pointer', color:'var(--gray-600)' }}>
          {loading ? '…' : '↻ Refresh'}
        </button>
      </div>
      <div className="search-sub" style={{ marginBottom:'1.5rem' }}>
        Semantic variants of previously verified claims — detected via embedding similarity.
        High-similarity variants share misinformation DNA regardless of surface wording.
      </div>

      {/* Legend */}
      <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:'1.25rem' }}>
        {[['≥0.80 similarity','var(--red)','High risk — near-identical claim'],
          ['0.65–0.79','var(--amber)','Moderate — paraphrased claim'],
          ['<0.65','var(--green)','Low — loosely related'],
        ].map(([label, color, tip]) => (
          <div key={label} style={{ display:'flex', alignItems:'center', gap:6, background:'var(--white)',
            border:'1px solid var(--gray-100)', borderRadius:8, padding:'5px 10px', fontSize:11, color:'var(--gray-600)' }}>
            <span style={{ width:10, height:10, borderRadius:'50%', background:color, flexShrink:0 }} />
            <strong style={{ color:'var(--gray-800)' }}>{label}</strong> — {tip}
          </div>
        ))}
      </div>

      {error && (
        <div style={{ background:'#fff5f5', border:'1px solid var(--red-border)', borderRadius:8, padding:'10px 14px', fontSize:13, color:'var(--red)', marginBottom:'1.25rem' }}>
          ⚠️ {error}
        </div>
      )}

      {loading && <div style={{ fontSize:13, color:'var(--gray-400)', padding:'2rem', textAlign:'center' }}>Loading mutation chains from backend…</div>}

      {!loading && !chains.length && !error && (
        <div style={{ fontSize:13, color:'var(--gray-400)', padding:'2rem', textAlign:'center', background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12 }}>
          No mutation chains detected yet.<br />
          <span style={{ fontSize:12 }}>Chains appear when verified claims contain a <code>mutation_chain</code> from the backend pipeline.</span>
        </div>
      )}

      {/* Chain cards */}
      {chains.map((chain, i) => (
        <div key={i} className="mutation-section" style={{
          background: chain.verdict === 'FALSE' ? '#fff7ed' : chain.verdict === 'TRUE' ? '#f0fdf4' : '#f8fafc',
          border: `1px solid ${chain.verdict === 'FALSE' ? 'var(--orange-border)' : chain.verdict === 'TRUE' ? '#bbf7d0' : 'var(--gray-100)'}`,
          borderRadius:12, padding:'1.25rem', marginBottom:'1rem',
        }}>
          {/* Header */}
          <div style={{ display:'flex', alignItems:'flex-start', gap:10, cursor:'pointer' }}
               onClick={() => toggle(i)}>
            <div style={{ flex:1 }}>
              <div className="mutation-chain-title" style={{ color: chain.verdict === 'FALSE' ? '#9a3412' : chain.verdict === 'TRUE' ? '#15803d' : 'var(--gray-600)' }}>
                🔀 Mutation Chain · {chain.variants.length} variant{chain.variants.length !== 1 ? 's' : ''}
              </div>
              <div style={{ fontWeight:600, fontSize:14, color:'var(--gray-900)', marginBottom:6, lineHeight:1.4 }}>
                "{chain.original}"
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
                <VerdictPill verdict={chain.verdict} />
                {chain.confidence !== null && (
                  <span style={{ fontFamily:"'DM Mono',monospace", fontSize:11, color:'var(--gray-500)' }}>
                    conf: {chain.confidence} · {chain.first_seen}
                  </span>
                )}
              </div>
            </div>
            <div style={{ fontSize:18, color:'var(--gray-400)', userSelect:'none', marginTop:2 }}>
              {expanded[i] ? '▲' : '▼'}
            </div>
          </div>

          {/* Variants list */}
          {expanded[i] && chain.variants.length > 0 && (
            <div style={{ marginTop:14, borderTop:`1px solid ${chain.verdict === 'FALSE' ? 'var(--orange-border)' : 'var(--gray-100)'}`, paddingTop:14 }}>
              <div style={{ fontSize:11, fontWeight:600, textTransform:'uppercase', letterSpacing:'0.07em',
                color:'var(--gray-400)', marginBottom:10 }}>
                Detected variants (by embedding similarity)
              </div>
              {chain.variants.map((v, j) => (
                <div key={j} className="mutation-variant">
                  <div className="mutation-variant-text">"{v.text}"</div>
                  <div style={{ display:'flex', alignItems:'center', gap:10, marginTop:6, flexWrap:'wrap' }}>
                    <SimilarityBar value={v.similarity} />
                    <VerdictPill verdict={v.verdict} />
                    <span className="mutation-sim">{v.date}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {expanded[i] && chain.variants.length === 0 && (
            <div style={{ marginTop:12, fontSize:12, color:'var(--gray-400)' }}>
              No variant chain data recorded for this claim.
            </div>
          )}
        </div>
      ))}

      <div style={{ fontSize:12, color:'var(--gray-400)', textAlign:'center', marginTop:8, padding:'0 1rem' }}>
        Chains detected via cosine similarity on 384-dim sentence embeddings (all-MiniLM-L6-v2). Threshold: 0.65.
      </div>
    </div>
  );
}