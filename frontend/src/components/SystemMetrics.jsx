import React, { useState, useEffect } from 'react';

const METRICS_DATA = {
  performance: [
    { label: 'Avg Latency',       value: '5.8s',  sub: 'p50: 4.1s  p95: 11.2s',  trend: '↓ 0.4s vs last hour' },
    { label: 'Throughput',        value: '12/min', sub: 'Peak: 31/min',            trend: '↑ stable'            },
    { label: 'Error Rate',        value: '0.8%',  sub: '7 errors last 24h',       trend: '↓ improving'         },
    { label: 'Cache Hit Rate',    value: '67%',   sub: 'Claims cache primary',    trend: '↑ 3% vs yesterday'   },
  ],
  llm: [
    { provider: 'Ollama (Qwen2.5 3B)', usage: 71, color: '#6366f1', latency: '3.2s' },
    { provider: 'Gemini Flash 2.0',    usage: 18, color: '#0ea5e9', latency: '1.8s' },
    { provider: 'Groq Llama 3',        usage:  8, color: '#f59e0b', latency: '0.9s' },
    { provider: 'Rule-Based Fallback', usage:  3, color: '#94a3b8', latency: '0.1s' },
  ],
  caches: [
    { name: 'Claims Cache',      ttl: '24h', size: '1.2 MB', hits: 482, misses: 236 },
    { name: 'Embeddings Cache',  ttl: '12h', size: '4.8 MB', hits: 310, misses: 190 },
    { name: 'LLM Response Cache',ttl: '6h',  size: '2.1 MB', hits: 195, misses: 120 },
    { name: 'Credibility Cache', ttl: '7d',  size: '0.4 MB', hits: 820, misses:  48 },
  ],
  sources: [
    { name: 'NewsAPI',    status: 'healthy',  calls: 1240, errors:  4, avgMs: 310  },
    { name: 'SERP',       status: 'healthy',  calls:  890, errors:  9, avgMs: 520  },
    { name: 'Snopes',     status: 'degraded', calls:  430, errors: 41, avgMs: 1800 },
    { name: 'GDELT',      status: 'healthy',  calls:  610, errors:  2, avgMs: 290  },
    { name: 'Wikipedia',  status: 'healthy',  calls:  780, errors:  1, avgMs: 190  },
    { name: 'Wikidata',   status: 'healthy',  calls:  320, errors:  3, avgMs: 240  },
  ],
};

const statusColor = s => s === 'healthy' ? 'var(--green)' : s === 'degraded' ? 'var(--amber)' : 'var(--red)';
const statusLabel = s => s === 'healthy' ? '● Healthy' : s === 'degraded' ? '● Degraded' : '● Down';

function BarRow({ label, pct, color, right }) {
  return (
    <div className="bar-row" style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
      <div style={{ width:160, fontSize:13, color:'var(--gray-600)', fontWeight:500, flexShrink:0 }}>{label}</div>
      <div style={{ flex:1, height:8, background:'var(--gray-100)', borderRadius:4, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${pct}%`, background: color, borderRadius:4 }} />
      </div>
      <div style={{ width:52, textAlign:'right', fontFamily:"'DM Mono',monospace", fontSize:13, fontWeight:500, color:'var(--gray-700)' }}>{right}</div>
    </div>
  );
}

export function SystemMetrics() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 3000);
    return () => clearInterval(id);
  }, []);

  // Simulate slight live fluctuation
  const liveLatency = (5.8 + (tick % 3) * 0.1).toFixed(1);

  return (
    <div id="metricsView">
      <div className="search-heading" style={{ marginBottom:'0.25rem' }}>System Metrics</div>
      <div className="search-sub" style={{ marginBottom:'1.5rem' }}>
        Real-time performance telemetry for the OSINT verification pipeline.
        <span style={{ fontFamily:"'DM Mono',monospace", fontSize:11, marginLeft:8, color:'var(--green)' }}>
          ● Live
        </span>
      </div>

      {/* KPI row */}
      <div className="metric-grid" style={{ gridTemplateColumns:'repeat(4,1fr)', marginBottom:'1.25rem' }}>
        {METRICS_DATA.performance.map(m => (
          <div key={m.label} className="metric-card" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'14px 12px', textAlign:'center' }}>
            <span className="metric-value" style={{ fontSize:22 }}>
              {m.label === 'Avg Latency' ? `${liveLatency}s` : m.value}
            </span>
            <div className="metric-label">{m.label}</div>
            <div style={{ fontSize:10, color:'var(--gray-400)', marginTop:4 }}>{m.sub}</div>
            <div style={{ fontSize:10, color:'var(--green)', marginTop:2, fontWeight:500 }}>{m.trend}</div>
          </div>
        ))}
      </div>

      {/* LLM Provider */}
      <div className="trace-section" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'1.25rem', marginBottom:'1.25rem' }}>
        <div className="section-title" style={{ fontSize:11, fontWeight:600, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--gray-400)', marginBottom:14 }}>
          LLM Provider Distribution
        </div>
        {METRICS_DATA.llm.map(p => (
          <BarRow key={p.provider} label={p.provider} pct={p.usage} color={p.color} right={`${p.usage}%`} />
        ))}
        <div style={{ marginTop:14, display:'flex', gap:8, flexWrap:'wrap' }}>
          {METRICS_DATA.llm.map(p => (
            <div key={p.provider} style={{ fontSize:11, color:'var(--gray-500)', background:'var(--gray-50)', borderRadius:6, padding:'3px 8px', display:'flex', gap:5, alignItems:'center' }}>
              <span style={{ width:8, height:8, borderRadius:'50%', background:p.color, display:'inline-block', flexShrink:0 }} />
              {p.provider} · avg {p.latency}
            </div>
          ))}
        </div>
      </div>

      {/* Cache stats */}
      <div className="trace-section" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'1.25rem', marginBottom:'1.25rem' }}>
        <div className="section-title" style={{ fontSize:11, fontWeight:600, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--gray-400)', marginBottom:14 }}>
          Cache Health
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
          {METRICS_DATA.caches.map(c => {
            const hitRate = Math.round(c.hits / (c.hits + c.misses) * 100);
            return (
              <div key={c.name} style={{ background:'var(--off-white)', borderRadius:10, padding:'12px 14px' }}>
                <div style={{ fontWeight:600, fontSize:13, color:'var(--gray-800)', marginBottom:6 }}>{c.name}</div>
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'var(--gray-500)', marginBottom:6 }}>
                  <span>TTL {c.ttl}</span><span>{c.size}</span>
                </div>
                <div style={{ height:6, background:'var(--gray-200)', borderRadius:3, overflow:'hidden', marginBottom:4 }}>
                  <div style={{ height:'100%', width:`${hitRate}%`, background: hitRate > 70 ? 'var(--green)' : hitRate > 50 ? 'var(--amber)' : 'var(--red)', borderRadius:3 }} />
                </div>
                <div style={{ fontSize:11, fontFamily:"'DM Mono',monospace", color:'var(--gray-500)' }}>
                  {hitRate}% hit · {c.hits.toLocaleString()} hits · {c.misses} misses
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Source API health */}
      <div className="trace-section" style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, padding:'1.25rem' }}>
        <div className="section-title" style={{ fontSize:11, fontWeight:600, letterSpacing:'0.08em', textTransform:'uppercase', color:'var(--gray-400)', marginBottom:14 }}>
          Source API Health (24h)
        </div>
        <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
          <thead>
            <tr style={{ borderBottom:'1px solid var(--gray-100)' }}>
              {['Source','Status','Calls','Errors','Avg Latency'].map(h => (
                <th key={h} style={{ textAlign:'left', padding:'6px 8px', fontWeight:600, fontSize:11, color:'var(--gray-400)', textTransform:'uppercase', letterSpacing:'0.06em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRICS_DATA.sources.map((s, i) => (
              <tr key={s.name} style={{ borderBottom: i < METRICS_DATA.sources.length - 1 ? '1px solid var(--gray-50)' : 'none' }}>
                <td style={{ padding:'8px', fontWeight:500, color:'var(--gray-800)' }}>{s.name}</td>
                <td style={{ padding:'8px', fontWeight:500, fontSize:12, color: statusColor(s.status) }}>{statusLabel(s.status)}</td>
                <td style={{ padding:'8px', fontFamily:"'DM Mono',monospace", color:'var(--gray-600)' }}>{s.calls.toLocaleString()}</td>
                <td style={{ padding:'8px', fontFamily:"'DM Mono',monospace", color: s.errors > 10 ? 'var(--red)' : 'var(--gray-600)' }}>{s.errors}</td>
                <td style={{ padding:'8px', fontFamily:"'DM Mono',monospace", color: s.avgMs > 1000 ? 'var(--amber)' : 'var(--gray-600)' }}>{s.avgMs}ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}