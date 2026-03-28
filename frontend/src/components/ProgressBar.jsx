import { useState, useEffect } from 'react';

const STAGES = [
  { progress: 20, label: "Scanning sources...", delay: 0 },
  { progress: 50, label: "Cross-referencing...", delay: 1000 },
  { progress: 85, label: "Finalizing verdict...", delay: 2500 },
];

export function ProgressBar({ loading }) {
  const [progress, setProgress] = useState(0);
  const [label, setLabel] = useState('');

  useEffect(() => {
    if (!loading) { setProgress(0); setLabel(''); return; }
    const timers = STAGES.map(stage =>
      setTimeout(() => {
        setProgress(stage.progress);
        setLabel(stage.label);
      }, stage.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [loading]);

  if (!loading) return null;

  return (
    <div style={{ marginTop: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#6b7280' }}>
        <span>{label}</span>
        <span>{progress}%</span>
      </div>
      <div style={{ height: '4px', backgroundColor: '#e5e7eb', borderRadius: '4px', marginTop: '4px' }}>
        <div style={{ 
          height: '100%', backgroundColor: '#2563eb', width: `${progress}%`, 
          transition: 'width 0.4s ease', borderRadius: '4px' 
        }} />
      </div>
    </div>
  );
}