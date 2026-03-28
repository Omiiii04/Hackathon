export function VerdictCard({ result }) {
  const isTrue = result.verdict === 'TRUE';
  const isUnverified = result.verdict === 'UNVERIFIED';
  
  // Decide glowing accents based on Fact-Check Result
  const colorVar = isTrue ? 'var(--neon-green)' : (isUnverified ? 'var(--neon-amber)' : 'var(--neon-red)');
  const glowVar = isTrue ? 'var(--neon-green-glow)' : (isUnverified ? 'var(--neon-amber-glow)' : 'var(--neon-red-glow)');

  return (
    <div className="glass-panel" style={{ padding: '30px', borderLeft: `6px solid ${colorVar}`, boxShadow: `0 10px 30px ${glowVar}`, transition: 'all 0.4s ease' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '25px' }}>
        <h2 style={{ margin: 0, fontSize: '36px', color: colorVar, letterSpacing: '2px', fontWeight: '800', textShadow: `0 0 15px ${glowVar}` }}>
          {result.verdict}
        </h2>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary)', letterSpacing: '2px', marginBottom: '6px' }}>CONFIDENCE SCORE</div>
          <div className="font-mono" style={{ fontSize: '28px', fontWeight: '800', color: 'var(--accent-blue)', textShadow: '0 0 10px var(--accent-blue-glow)' }}>
            {Math.round(result.confidence * 100)}%
          </div>
        </div>
      </div>
      <p style={{ color: 'var(--text-primary)', lineHeight: '1.7', fontSize: '16px', margin: 0, fontWeight: '400' }}>
        {result.explanation}
      </p>
    </div>
  );
}