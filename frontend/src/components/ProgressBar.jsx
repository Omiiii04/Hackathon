import { useState, useEffect } from 'react';

const STAGES = [
  { progress: 18, label: 'Extracting entities & claim type…',  delay: 0    },
  { progress: 45, label: 'Querying sources in parallel…',      delay: 900  },
  { progress: 75, label: 'Running cross-reference scoring…',   delay: 2100 },
  { progress: 92, label: 'Generating verdict explanation…',    delay: 3400 },
];

export function ProgressBar({ loading }) {
  const [progress, setProgress]   = useState(0);
  const [label, setLabel]         = useState('');
  const [stageIdx, setStageIdx]   = useState(0);

  useEffect(() => {
    if (!loading) {
      setProgress(0);
      setLabel('');
      setStageIdx(0);
      return;
    }
    const timers = STAGES.map((stage, i) =>
      setTimeout(() => {
        setProgress(stage.progress);
        setLabel(stage.label);
        setStageIdx(i);
      }, stage.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading]);

  if (!loading) return null;

  return (
    <div className="progress-section visible" style={{ marginTop: '12px' }}>
      {/* Stage indicator row */}
      <div className="progress-stage">
        <span style={{ color: 'var(--ink)', fontWeight: 500 }}>Analysing</span>
        <span>{label}</span>
      </div>

      {/* Segment dots */}
      <div className="progress-steps" style={{ marginBottom: '8px' }}>
        {STAGES.map((_, i) => (
          <div
            key={i}
            className={`progress-step${i <= stageIdx ? ' done' : ''}`}
            style={{
              flex: 1,
              height: '3px',
              borderRadius: '2px',
              background: i <= stageIdx ? 'var(--accent)' : 'var(--gray-100)',
              transition: 'background 0.4s ease',
              marginRight: i < STAGES.length - 1 ? '4px' : 0,
            }}
          />
        ))}
      </div>

      {/* Main bar */}
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Percentage label */}
      <div
        style={{
          marginTop: '6px',
          textAlign: 'right',
          fontFamily: "'DM Mono', monospace",
          fontSize: '11px',
          color: 'var(--gray-400)',
        }}
      >
        {progress}%
      </div>
    </div>
  );
}
