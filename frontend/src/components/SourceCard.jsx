import React from 'react';

export default function SourceCard({ source }) {
  return (
    <div style={{ 
      padding: '10px', 
      marginBottom: '8px',
      backgroundColor: '#0f172a',
      borderRadius: '6px',
      borderLeft: `4px solid ${source.verdict === 'SUPPORTING' ? '#22c55e' : '#ef4444'}`,
      fontSize: '12px' 
    }}>
      <div style={{ fontWeight: 'bold', color: '#f8fafc', marginBottom: '4px' }}>{source.name || "News Source"}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <a href={source.url} target="_blank" rel="noreferrer" style={{ color: '#3b82f6', textDecoration: 'none' }}>
          🔗 View Evidence
        </a>
        <span style={{ fontSize: '10px', color: '#94a3b8' }}>MATCH: {source.verdict}</span>
      </div>
    </div>
  );
}