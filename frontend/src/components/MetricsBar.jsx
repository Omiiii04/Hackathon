import React, { useState, useEffect } from 'react';

export function MetricsBar() {
  const [time, setTime] = useState(new Date().toLocaleTimeString('en-GB'));
  const [date, setDate] = useState(
    new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
  );

  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setTime(now.toLocaleTimeString('en-GB'));
      setDate(now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header>
      {/* Logo */}
      <div className="logo">
        <div className="logo-icon">🛡️</div>
        <div className="logo-text">
          OSINT <span>Verify</span>
        </div>
      </div>

      {/* Nav */}
      <nav>
        <button className="nav-btn active" onClick={() => window.switchView?.('verify')}>
          Verify
        </button>
        <button className="nav-btn" onClick={() => window.switchView?.('dashboard')}>
          Dashboard
        </button>
      </nav>

      {/* Right side — status + clock */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--gray-600)',
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: 'var(--green)',
              display: 'inline-block',
            }}
          />
          Systems Operational
        </div>

        <div
          style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: '13px',
            color: 'var(--gray-600)',
            letterSpacing: '0.04em',
          }}
        >
          {time} · {date}
        </div>

        <div
          className="profile-badge"
          onClick={() => window.cycleProfile?.()}
          title="Click to cycle profile"
        >
          <div className="profile-dot" />
          <span id="profileLabel">General</span>
          <span style={{ color: 'var(--gray-400)', fontSize: '11px' }}>▾</span>
        </div>
      </div>
    </header>
  );
}
