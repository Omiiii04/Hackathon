import React, { useState, useEffect, useCallback } from 'react';

const LOCAL_KEY = 'osint_history';
const MAX_ITEMS = 50;

// ── Local storage helpers ─────────────────────────────────
function loadLocal() {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveLocal(items) {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
  } catch {
    // storage full — ignore
  }
}

export function History({ refreshTrigger, lastResult }) {
  const [historyData, setHistoryData] = useState(() => loadLocal());

  // Try to sync from backend; fall back silently to local data
  const syncFromBackend = useCallback(async () => {
    try {
      const res = await fetch('http://localhost:8000/history', { signal: AbortSignal.timeout(3000) });
      if (res.ok) {
        const data = await res.json();
        const remote = data.history || [];
        if (remote.length > 0) {
          setHistoryData(remote);
          saveLocal(remote);
        }
      }
    } catch {
      // Backend offline — stay on local data, no error shown
    }
  }, []);

  // On mount: load local immediately, then try backend
  useEffect(() => {
    const local = loadLocal();
    if (local.length > 0) setHistoryData(local);
    syncFromBackend();
  }, []);

  // When a new verification finishes, add it locally right away
  useEffect(() => {
    if (!lastResult) return;

    const newEntry = {
      claim:     lastResult.claim_text || lastResult.claim || '(unknown)',
      verdict:   lastResult.verdict    || 'UNVERIFIED',
      timestamp: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }),
    };

    setHistoryData(prev => {
      const updated = [newEntry, ...prev].slice(0, MAX_ITEMS);
      saveLocal(updated);
      return updated;
    });

    // Also attempt a background sync from backend after a short delay
    setTimeout(syncFromBackend, 800);
  }, [refreshTrigger, lastResult, syncFromBackend]);

  const handleClear = async () => {
    if (!window.confirm('Clear all history logs?')) return;

    // Clear locally first so UI responds instantly
    setHistoryData([]);
    saveLocal([]);

    // Also clear on backend if reachable
    try {
      await fetch('http://localhost:8000/history/clear', {
        method: 'DELETE',
        signal: AbortSignal.timeout(3000),
      });
    } catch {
      // Backend offline — local clear is enough
    }
  };

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