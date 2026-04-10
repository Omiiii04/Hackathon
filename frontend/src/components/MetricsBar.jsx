import React, { useState, useEffect } from 'react';

const NAV_ITEMS = [
  { id: 'verify',             label: 'Verify',             icon: '🔍' },
  { id: 'dashboard',          label: 'Dashboard',          icon: '📊' },
  { id: 'metrics',            label: 'System Metrics',     icon: '📈' },
  { id: 'mutation-chains',    label: 'Mutation Chains',    icon: '🔀' },
  { id: 'source-credibility', label: 'Source Credibility', icon: '🌐' },
];

export function MetricsBar({ currentView, onViewChange, currentProfile, onProfileChange }) {
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

  const profileLabels = { general: 'General', journalist: 'Journalist', researcher: 'Researcher' };

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
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`nav-btn ${currentView === item.id ? 'active' : ''}`}
            onClick={() => onViewChange(item.id)}
            title={item.label}
          >
            <span style={{ marginRight: 5 }}>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Right side — status + clock + profile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--gray-600)' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
          Systems Operational
        </div>

        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: '13px', color: 'var(--gray-600)', letterSpacing: '0.04em' }}>
          {time} · {date}
        </div>

        <div
          className="profile-badge"
          onClick={onProfileChange}
          title="Click to cycle profile"
        >
          <div className="profile-dot" />
          <span>{profileLabels[currentProfile] || 'General'}</span>
          <span style={{ color: 'var(--gray-400)', fontSize: '11px' }}>▾</span>
        </div>
      </div>
    </header>
  );
}