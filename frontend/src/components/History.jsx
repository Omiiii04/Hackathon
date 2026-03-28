import React, { useState, useEffect } from 'react';

export function History({ refreshTrigger }) {
  const [historyData, setHistoryData] = useState([]);

  // 1. Function to fetch data
  const fetchHistory = async () => {
    try {
      const response = await fetch('http://localhost:8000/history');
      if (response.ok) {
        const data = await response.json();
        setHistoryData(data.history || []);
      }
    } catch (error) {
      console.error("Fetch error:", error);
    }
  };

  // 2. Function to CLEAR data
const handleClear = async () => {
    if (!window.confirm("Clear all logs?")) return;

    try {
      // The URL and the { method } object MUST be inside the same fetch() parentheses
      const response = await fetch('http://localhost:8000/history/clear', {
        method: 'DELETE',
      });

      const data = await response.json();

      if (response.ok && data.status === "success") {
        setHistoryData([]); 
      } else {
        alert("Server failed to clear history");
      }
    } catch (error) {
      console.error("Network error:", error);
      alert("Could not connect to backend to clear history.");
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [refreshTrigger]); // This is key: it re-fetches when a new claim is verified

  return (
    <div className="glass-panel" style={{ padding: '30px', marginTop: '40px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '25px' }}>
        <h3 style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '15px', letterSpacing: '2px' }}>SYSTEM HISTORY LOGS</h3>
        
        {historyData.length > 0 && (
          <button 
            className="neon-button"
            onClick={handleClear}
            style={{ 
              width: 'auto',
              background: 'rgba(239, 68, 68, 0.1)', 
              color: 'var(--neon-red)', 
              borderColor: 'var(--neon-red)',
              padding: '10px 20px', 
              boxShadow: '0 0 10px var(--neon-red-glow)',
              fontSize: '13px'
            }}
          >
            🗑️ CLEAR ALL
          </button>
        )}
      </div>

      <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '2px solid var(--glass-border)', color: 'var(--text-muted)', fontSize: '13px', letterSpacing: '1px' }}>
              <th style={{ padding: '15px' }}>TIMESTAMP</th>
              <th style={{ padding: '15px' }}>CLAIM</th>
              <th style={{ padding: '15px' }}>VERDICT</th>
            </tr>
          </thead>
          <tbody>
            {historyData.length === 0 ? (
              <tr>
                <td colSpan="3" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No historical telemetry logs found.
                </td>
              </tr>
            ) : (
              historyData.map((item, i) => {
                const isTrue = item.verdict === 'TRUE';
                const color = isTrue ? 'var(--neon-green)' : (item.verdict === 'UNVERIFIED' ? 'var(--neon-amber)' : 'var(--neon-red)');
                return (
                  <tr key={i} style={{ borderBottom: '1px solid var(--glass-border)', transition: 'background 0.2s' }} onMouseOver={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'} onMouseOut={e => e.currentTarget.style.background = 'transparent'}>
                    <td className="font-mono" style={{ padding: '16px', color: 'var(--text-muted)', fontSize: '13px' }}>{item.timestamp}</td>
                    <td style={{ padding: '16px', color: 'var(--text-primary)', maxWidth: '400px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.claim}</td>
                    <td style={{ padding: '16px', fontWeight: '800', color: color, textShadow: `0 0 10px ${color}` }}>
                      {item.verdict}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}