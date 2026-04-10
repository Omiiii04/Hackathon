import React, { useState } from 'react';

const DEMO_CHAINS = [
  {
    original: '5G towers cause COVID-19 symptoms',
    verdict: 'FALSE',
    confidence: 0.94,
    first_seen: '2020-03-18',
    variants: [
      { text: 'Radiation from cell towers causes flu-like illness', similarity: 0.82, verdict: 'FALSE', date: '2020-04-10' },
      { text: 'WiFi signals weaken the immune system against viruses', similarity: 0.76, verdict: 'FALSE', date: '2020-02-03' },
      { text: '5G rollout correlates with pandemic hotspots', similarity: 0.71, verdict: 'FALSE', date: '2020-05-22' },
      { text: 'Millimeter wave radiation linked to respiratory illness', similarity: 0.68, verdict: 'FALSE', date: '2020-06-01' },
    ],
    tags: ['Debunked ×4', 'High mutation rate', 'Echo chamber detected'],
  },
  {
    original: 'Vaccines contain microchips for tracking',
    verdict: 'FALSE',
    confidence: 0.97,
    first_seen: '2021-01-05',
    variants: [
      { text: 'mRNA vaccines alter human DNA permanently', similarity: 0.79, verdict: 'FALSE', date: '2021-02-14' },
      { text: 'COVID vaccine contains graphene oxide nano-particles', similarity: 0.74, verdict: 'FALSE', date: '2021-04-30' },
      { text: 'Bill Gates funded vaccine includes surveillance tech', similarity: 0.69, verdict: 'FALSE', date: '2021-03-10' },
    ],
    tags: ['Debunked ×3', 'Cross-platform spread', 'Coordinated amplification'],
  },
  {
    original: 'WHO declared mpox a global health emergency',
    verdict: 'TRUE',
    confidence: 0.91,
    first_seen: '2024-08-14',
    variants: [
      { text: 'Monkeypox declared Public Health Emergency of International Concern', similarity: 0.95, verdict: 'TRUE', date: '2024-08-14' },
      { text: 'WHO raises mpox alert to highest level', similarity: 0.88, verdict: 'TRUE', date: '2024-08-15' },
    ],
    tags: ['Confirmed true', 'Semantic variants only', 'Low risk'],
  },
  {
    original: 'Parliament passed new surveillance bill secretly',
    verdict: 'UNVERIFIED',
    confidence: 0.52,
    first_seen: '2024-11-02',
    variants: [
      { text: 'Government introduced mass surveillance legislation', similarity: 0.77, verdict: 'UNVERIFIED', date: '2024-11-03' },
      { text: 'New law allows agencies to monitor all internet traffic', similarity: 0.71, verdict: 'MISLEADING', date: '2024-11-05' },
    ],
    tags: ['Unverified origin', 'Escalating mutation', 'Monitor'],
  },
];

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
  const pct = Math.round(value * 100);
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

export function MutationChains() {
  const [expanded, setExpanded] = useState({ 0: true });

  const toggle = (i) => setExpanded(prev => ({ ...prev, [i]: !prev[i] }));

  return (
    <div id="mutationChainsView">
      <div className="search-heading" style={{ marginBottom:'0.25rem' }}>Mutation Chains</div>
      <div className="search-sub" style={{ marginBottom:'1.5rem' }}>
        Semantic variants of previously verified claims — detected via embedding similarity. High-similarity
        variants share misinformation DNA regardless of surface wording.
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

      {/* Chain cards */}
      {DEMO_CHAINS.map((chain, i) => (
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
                <span style={{ fontFamily:"'DM Mono',monospace", fontSize:11, color:'var(--gray-500)' }}>
                  conf: {chain.confidence} · first seen {chain.first_seen}
                </span>
              </div>
              <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginTop:8 }}>
                {chain.tags.map(t => (
                  <span key={t} style={{ fontSize:10, background:'var(--gray-100)', color:'var(--gray-600)',
                    borderRadius:4, padding:'2px 7px', fontWeight:500 }}>{t}</span>
                ))}
              </div>
            </div>
            <div style={{ fontSize:18, color:'var(--gray-400)', userSelect:'none', marginTop:2 }}>
              {expanded[i] ? '▲' : '▼'}
            </div>
          </div>

          {/* Variants list */}
          {expanded[i] && (
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
        </div>
      ))}

      {/* Footer note */}
      <div style={{ fontSize:12, color:'var(--gray-400)', textAlign:'center', marginTop:8, padding:'0 1rem' }}>
        Chains are generated via cosine similarity on 384-dim sentence embeddings (all-MiniLM-L6-v2).
        Threshold: 0.65.
      </div>
    </div>
  );
}