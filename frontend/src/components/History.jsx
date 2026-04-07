import React, { useState, useEffect } from 'react';

export function History({ refreshTrigger }) {
  const [historyData, setHistoryData] = useState([]);

  const fetchHistory = async () => {
    try {
      const response = await fetch('http://localhost:8000/history');
      if (response.ok) {
        const data = await response.json();
        setHistoryData(data.history || []);
      }
    } catch (error) {
      console.error('Fetch error:', error);
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Clear all history logs?')) return;
    try {
      const response = await fetch('http://localhost:8000/history/clear', { method: 'DELETE' });
      const data = await response.json();
      if (response.ok && data.status === 'success') setHistoryData([]);
      else alert('Server failed to clear history.');
    } catch {
      alert('Could not connect to backend.');
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [refreshTrigger]);

  return (
    <div className="sidebar-section">
      {/* Section header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '8px',
          paddingLeft: '8px',
          paddingRight: '4px',
        }}
      >
        <span className="sidebar-label" style={{ margin: 0 }}>
          Recent
        </span>
        {historyData.length > 0 && (
          <button
            onClick={handleClear}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              color: 'var(--gray-400)',
              padding: '2px 4px',
              borderRadius: '4px',
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--red)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--gray-400)')}
            title="Clear all history"
          >
            Clear
          </button>
        )}
      </div>

      {/* History list */}
      {historyData.length === 0 ? (
        <div
          style={{
            padding: '20px 10px',
            textAlign: 'center',
            color: 'var(--gray-400)',
            fontSize: '12px',
          }}
        >
          No recent checks
        </div>
      ) : (
        historyData.map((item, i) => (
          <div key={i} className="history-item">
            <div className="history-claim">{item.claim}</div>
            <div className="history-meta">
              <span className={`verdict-pill v-${item.verdict}`}>{item.verdict}</span>
              <span className="history-time">{item.timestamp}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
