import React from 'react';

const TIER_ICONS = { 1: '🏛️', 2: '📰', 3: '📄', 4: '🌐', 5: '⚠️' };

export default function SourceCard({ source, index = 0 }) {
  const isSupporting = source.stance === 'SUPPORTING';
  const isContradicting = source.stance === 'CONTRADICTING';

  return (
    <div className="source-card">
      {/* Favicon / tier icon */}
      <div className="source-favicon">
        {TIER_ICONS[source.tier] || '🌐'}
      </div>

      {/* Info */}
      <div className="source-info">
        <div className="source-name">{source.name || source.domain}</div>
        <div className="source-meta">
          <span className={`tier-badge t${source.tier}`}>T{source.tier}</span>
          <span className="source-date">{source.date}</span>
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              style={{
                fontSize: '11px',
                color: 'var(--accent)',
                textDecoration: 'none',
                fontFamily: "'DM Mono', monospace",
              }}
              onMouseEnter={e => (e.currentTarget.style.textDecoration = 'underline')}
              onMouseLeave={e => (e.currentTarget.style.textDecoration = 'none')}
            >
              View →
            </a>
          )}
        </div>
        <div className="credibility-bar-mini">
          <div
            className="credibility-fill"
            style={{
              width: `${Math.round((source.credibility ?? 0.5) * 100)}%`,
              background: isSupporting
                ? 'var(--green)'
                : isContradicting
                ? 'var(--red)'
                : 'var(--gray-400)',
            }}
          />
        </div>
      </div>

      {/* Stance dot + credibility shift */}
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div className={`source-stance ss-${source.stance}`} style={{ marginLeft: 'auto' }} />
        {source.shift !== undefined && source.shift !== 0 && (
          <div className={`credibility-shift ${source.shift > 0 ? 'shift-up' : 'shift-down'}`}>
            {source.shift > 0 ? '↑' : '↓'}{Math.abs(source.shift).toFixed(2)}
          </div>
        )}
      </div>
    </div>
  );
}
