import React, { useEffect, useState } from 'react';

const CONF_COLORS = {
  TRUE:        '#15803d',
  FALSE:       '#991b1b',
  MISLEADING:  '#92400e',
  CONFLICTING: '#9a3412',
  UNVERIFIED:  '#374151',
};

function ConfidenceRing({ value, verdict }) {
  const r      = 34;
  const circ   = 2 * Math.PI * r;
  const color  = CONF_COLORS[verdict] || '#374151';
  const [offset, setOffset] = useState(circ);

  useEffect(() => {
    const t = setTimeout(() => setOffset(circ * (1 - value)), 120);
    return () => clearTimeout(t);
  }, [value, circ]);

  return (
    <div className="confidence-ring">
      <svg
        className="confidence-svg"
        width="80"
        height="80"
        viewBox="0 0 80 80"
      >
        <circle className="confidence-bg" cx="40" cy="40" r={r} />
        <circle
          className="confidence-fg"
          cx="40"
          cy="40"
          r={r}
          stroke={color}
          strokeDasharray={circ}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="confidence-text">
        <span className="confidence-pct">{Math.round(value * 100)}%</span>
        <span className="confidence-lbl">conf.</span>
      </div>
    </div>
  );
}

export function VerdictCard({ result }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 60);
    return () => clearTimeout(t);
  }, [result]);

  if (!result) return null;

  const { verdict, confidence, claim_text, explanation, claim_type, processing_ms, cached, verdict_tags } = result;

  const emojis     = { TRUE: '✅', FALSE: '❌', MISLEADING: '⚠️', CONFLICTING: '🔀', UNVERIFIED: '❓' };
  const ctIcons    = { breaking_news: '⚡', scientific: '🔬', political: '🏛️', general: '📄' };

  return (
    <div
      className={`verdict-card vc-${verdict}`}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(12px)',
        transition: 'opacity 0.4s ease, transform 0.4s cubic-bezier(0.22,1,0.36,1)',
      }}
    >
      <div className="verdict-top">
        {/* Left */}
        <div className="verdict-left">
          <div className="verdict-emoji">{emojis[verdict]}</div>

          {claim_type && (
            <div className="claim-type-badge" id="claimTypeBadge">
              {ctIcons[claim_type] || '📄'} {claim_type.replace('_', ' ')}
            </div>
          )}

          <div className={`verdict-label vl-${verdict}`} id="verdictLabel">
            {verdict}
          </div>

          {claim_text && (
            <div className="verdict-claim-text" id="verdictClaim">
              "{claim_text}"
            </div>
          )}

          {/* Meta row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '10px', flexWrap: 'wrap' }}>
            {cached && (
              <span
                id="cachedBadge"
                style={{
                  fontSize: '11px',
                  background: 'var(--accent-light)',
                  color: 'var(--accent)',
                  padding: '2px 8px',
                  borderRadius: '10px',
                  fontWeight: 500,
                }}
              >
                ⚡ Cached
              </span>
            )}
            {processing_ms != null && (
              <span
                id="processingTime"
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: '11px',
                  color: 'var(--gray-400)',
                }}
              >
                {processing_ms.toLocaleString()} ms
              </span>
            )}
          </div>
        </div>

        {/* Right — confidence ring */}
        <div className="verdict-right">
          <ConfidenceRing value={confidence ?? 0} verdict={verdict} />
        </div>
      </div>

      {/* Explanation */}
      {explanation && (
        <p
          id="explanationText"
          style={{
            fontSize: '14px',
            color: 'var(--gray-800)',
            lineHeight: '1.7',
            marginTop: '14px',
          }}
        >
          {explanation}
        </p>
      )}

      {/* Tags */}
      {verdict_tags && verdict_tags.length > 0 && (
        <div className="verdict-tags" id="verdictTags">
          {verdict_tags.map((tag, i) => (
            <span key={i} className="vtag">{tag}</span>
          ))}
        </div>
      )}
    </div>
  );
}
