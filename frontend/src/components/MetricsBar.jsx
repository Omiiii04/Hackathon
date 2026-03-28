import React, { useState, useEffect } from 'react';

export function MetricsBar() {
  const [time, setTime] = useState(new Date().toLocaleTimeString('en-GB'));

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString('en-GB')), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="glass-panel" style={{
      borderRadius: '0 0 24px 24px',
      borderTop: 'none',
      padding: '20px 40px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: '30px',
      boxShadow: '0 10px 30px rgba(0,0,0,0.6)'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '15px',
        fontSize: '24px',
        fontWeight: '800',
        letterSpacing: '3px'
      }}>
        <div style={{
          background: 'linear-gradient(135deg, #60a5fa, #3b82f6)',
          padding: '8px',
          borderRadius: '12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px var(--accent-blue-glow)'
        }}>
          <span style={{ fontSize: '20px', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.4))' }}>🛡️</span>
        </div>
        <span className="text-gradient" style={{ textShadow: '0 0 20px var(--accent-blue-glow)' }}>
          OSINT Engine
        </span>
      </div>

      <div className="font-mono text-gradient" style={{
        fontSize: '32px',
        fontWeight: '700',
        letterSpacing: '2px',
        textShadow: '0 0 15px var(--accent-blue-glow)'
      }}>
        {time}
      </div>
    </div>
  );
}