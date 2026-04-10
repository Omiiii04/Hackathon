import React, { useState } from 'react';

const SOURCES = [
  { name:'WHO',              domain:'who.int',          tier:1, credibility:0.97, category:'Health',      country:'International', shift:+0.02, notes:'Primary global health authority' },
  { name:'CDC',              domain:'cdc.gov',          tier:1, credibility:0.96, category:'Health',      country:'USA',           shift:0,     notes:'US public health agency' },
  { name:'Reuters',          domain:'reuters.com',      tier:1, credibility:0.93, category:'News',        country:'UK',            shift:+0.01, notes:'Wire service, strong editorial standards' },
  { name:'AP News',          domain:'apnews.com',       tier:1, credibility:0.95, category:'News',        country:'USA',           shift:+0.01, notes:'Non-profit wire service' },
  { name:'BBC',              domain:'bbc.com',          tier:1, credibility:0.94, category:'News',        country:'UK',            shift:0,     notes:'UK public broadcaster' },
  { name:'Nature',           domain:'nature.com',       tier:1, credibility:0.98, category:'Science',     country:'International', shift:+0.01, notes:'Peer-reviewed scientific journal' },
  { name:'PubMed',           domain:'pubmed.ncbi.nlm.nih.gov', tier:1, credibility:0.97, category:'Science', country:'USA',      shift:0,     notes:'NIH biomedical literature index' },
  { name:'The Guardian',     domain:'guardian.com',     tier:2, credibility:0.82, category:'News',        country:'UK',            shift:-0.01, notes:'Independent news outlet' },
  { name:'NYT',              domain:'nytimes.com',      tier:2, credibility:0.85, category:'News',        country:'USA',           shift:0,     notes:'Legacy broadsheet' },
  { name:'Snopes',           domain:'snopes.com',       tier:2, credibility:0.84, category:'Fact-check',  country:'USA',           shift:-0.02, notes:'Dedicated fact-checking site' },
  { name:'PolitiFact',       domain:'politifact.com',   tier:2, credibility:0.83, category:'Fact-check',  country:'USA',           shift:0,     notes:'Political fact-checking' },
  { name:'GDELT',            domain:'gdeltproject.org', tier:2, credibility:0.78, category:'Data',        country:'International', shift:+0.01, notes:'Global event database' },
  { name:'Wikipedia',        domain:'wikipedia.org',    tier:3, credibility:0.72, category:'Reference',   country:'International', shift:+0.01, notes:'Crowd-sourced, use with caution' },
  { name:'The Daily Mail',   domain:'dailymail.co.uk',  tier:3, credibility:0.45, category:'News',        country:'UK',            shift:-0.03, notes:'Tabloid, low accuracy history' },
  { name:'InfoWars',         domain:'infowars.com',     tier:4, credibility:0.08, category:'Conspiracy',  country:'USA',           shift:-0.05, notes:'Known misinformation source' },
  { name:'Unknown Blog',     domain:'healthtruth.net',  tier:4, credibility:0.28, category:'Blog',        country:'Unknown',       shift:-0.03, notes:'Unverified, no editorial oversight' },
];

const TIER_INFO = {
  1: { label:'Tier 1 — Authoritative', color:'#15803d', bg:'#dcfce7', desc:'Peer-reviewed or government sources with rigorous editorial standards.' },
  2: { label:'Tier 2 — Credible',      color:'#1d4ed8', bg:'#dbeafe', desc:'Established outlets with editorial oversight. Occasional bias possible.' },
  3: { label:'Tier 3 — Mixed',         color:'#92400e', bg:'#fef3c7', desc:'Variable reliability; cross-reference with tier 1–2 sources.' },
  4: { label:'Tier 4 — Unreliable',    color:'#b91c1c', bg:'#fee2e2', desc:'Known for misinformation, conspiracy content, or zero editorial review.' },
};

const CATEGORIES = ['All', ...Array.from(new Set(SOURCES.map(s => s.category)))];

function CredBar({ score }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'var(--green)' : pct >= 60 ? 'var(--amber)' : pct >= 40 ? 'var(--orange)' : 'var(--red)';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
      <div style={{ width:80, height:6, background:'var(--gray-200)', borderRadius:3, overflow:'hidden' }}>
        <div style={{ height:'100%', width:`${pct}%`, background:color, borderRadius:3 }} />
      </div>
      <span style={{ fontFamily:"'DM Mono',monospace", fontSize:12, fontWeight:500, color:'var(--gray-700)', minWidth:32 }}>{score.toFixed(2)}</span>
    </div>
  );
}

function ShiftBadge({ shift }) {
  if (shift === 0) return <span style={{ fontFamily:"'DM Mono',monospace", fontSize:11, color:'var(--gray-400)' }}>—</span>;
  const up = shift > 0;
  return (
    <span className={`credibility-shift ${up ? 'shift-up' : 'shift-down'}`}>
      {up ? `▲ +${shift.toFixed(2)}` : `▼ ${shift.toFixed(2)}`}
    </span>
  );
}

export function SourceCredibility() {
  const [selectedTier, setSelectedTier] = useState('All');
  const [selectedCat, setSelectedCat]   = useState('All');
  const [sortBy, setSortBy]             = useState('credibility');

  const filtered = SOURCES
    .filter(s => (selectedTier === 'All' || String(s.tier) === String(selectedTier)))
    .filter(s => (selectedCat  === 'All' || s.category === selectedCat))
    .sort((a, b) => sortBy === 'credibility' ? b.credibility - a.credibility : a.tier - b.tier);

  return (
    <div id="sourceCredibilityView">
      <div className="search-heading" style={{ marginBottom:'0.25rem' }}>Source Credibility</div>
      <div className="search-sub" style={{ marginBottom:'1.5rem' }}>
        Credibility scores are computed from historical accuracy, editorial standards, and community fact-checks.
        Scores update weekly via automated analysis.
      </div>

      {/* Tier legend */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:'1.25rem' }}>
        {Object.entries(TIER_INFO).map(([tier, info]) => (
          <div key={tier} style={{ background:info.bg, borderRadius:10, padding:'10px 14px',
            cursor:'pointer', outline: selectedTier === tier ? `2px solid ${info.color}` : 'none',
            outlineOffset:1 }}
            onClick={() => setSelectedTier(selectedTier === tier ? 'All' : tier)}>
            <div style={{ fontWeight:700, fontSize:12, color:info.color, marginBottom:3 }}>{info.label}</div>
            <div style={{ fontSize:11, color:'var(--gray-600)' }}>{info.desc}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginBottom:'1.25rem', alignItems:'center' }}>
        <div style={{ fontSize:11, fontWeight:600, color:'var(--gray-400)', textTransform:'uppercase', letterSpacing:'0.06em' }}>Filter:</div>
        {CATEGORIES.map(c => (
          <div key={c}
            className={`claim-type-tag ${selectedCat === c ? 'selected' : ''}`}
            onClick={() => setSelectedCat(c)}
            style={{ fontSize:11, padding:'3px 10px' }}>
            {c}
          </div>
        ))}
        <div style={{ marginLeft:'auto', display:'flex', gap:6, alignItems:'center', fontSize:11, color:'var(--gray-500)' }}>
          Sort:
          {['credibility','tier'].map(s => (
            <div key={s}
              className={`claim-type-tag ${sortBy === s ? 'selected' : ''}`}
              onClick={() => setSortBy(s)}
              style={{ fontSize:11, padding:'3px 10px', textTransform:'capitalize' }}>
              {s}
            </div>
          ))}
        </div>
      </div>

      {/* Source table */}
      <div style={{ background:'var(--white)', border:'1px solid var(--gray-100)', borderRadius:12, overflow:'hidden' }}>
        <table style={{ width:'100%', borderCollapse:'collapse', fontSize:13 }}>
          <thead>
            <tr style={{ borderBottom:'1px solid var(--gray-100)', background:'var(--off-white)' }}>
              {['Source','Tier','Category','Credibility Score','30d Shift','Notes'].map(h => (
                <th key={h} style={{ textAlign:'left', padding:'10px 12px', fontWeight:600, fontSize:10,
                  color:'var(--gray-400)', textTransform:'uppercase', letterSpacing:'0.07em' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((s, i) => {
              const ti = TIER_INFO[s.tier];
              return (
                <tr key={s.domain} style={{ borderBottom: i < filtered.length - 1 ? '1px solid var(--gray-50)' : 'none' }}>
                  <td style={{ padding:'10px 12px' }}>
                    <div style={{ fontWeight:600, color:'var(--gray-900)' }}>{s.name}</div>
                    <div style={{ fontSize:11, color:'var(--gray-400)', fontFamily:"'DM Mono',monospace" }}>{s.domain}</div>
                  </td>
                  <td style={{ padding:'10px 12px' }}>
                    <span className={`tier-badge t${s.tier}`}
                      style={ s.tier === 4 ? { background:'#fee2e2', color:'#b91c1c' } : {} }>
                      T{s.tier}
                    </span>
                  </td>
                  <td style={{ padding:'10px 12px', fontSize:12, color:'var(--gray-600)' }}>{s.category}</td>
                  <td style={{ padding:'10px 12px' }}>
                    <CredBar score={s.credibility} />
                  </td>
                  <td style={{ padding:'10px 12px' }}>
                    <ShiftBadge shift={s.shift} />
                  </td>
                  <td style={{ padding:'10px 12px', fontSize:11, color:'var(--gray-500)', maxWidth:180 }}>{s.notes}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div style={{ padding:'2rem', textAlign:'center', color:'var(--gray-400)', fontSize:13 }}>
            No sources match the selected filters.
          </div>
        )}
      </div>

      <div style={{ fontSize:11, color:'var(--gray-400)', textAlign:'center', marginTop:12 }}>
        {filtered.length} of {SOURCES.length} sources shown · Scores updated weekly via automated fact-check analysis
      </div>
    </div>
  );
}