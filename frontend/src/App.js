import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MetricsBar } from './components/MetricsBar';
import { History } from './components/History';
import { ProgressBar } from './components/ProgressBar';
import { VerdictCard } from './components/VerdictCard';
import SourceCard from './components/SourceCard';
import './style.css'; // Global Design System

export default function App() {
  const [claim, setClaim] = useState("");
  const [selectedImage, setSelectedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isDragging, setIsDragging] = useState(false); // Drag & Drop State
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const fileInputRef = useRef(null);

  // Handle Input Browser Change
  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedImage(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  // Drag and Drop Handlers
  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };
  const handleDragLeave = () => setIsDragging(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedImage(file);
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleVerify = async () => {
    if (!claim && !selectedImage) {
      alert("Please enter a claim or upload an image.");
      return;
    }

    setLoading(true);
    const API_URL = "http://localhost:8000/verify";

    try {
      let base64Image = null;
      if (selectedImage) {
        base64Image = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = (e) => resolve(e.target.result);
          reader.onerror = (e) => reject(e);
          reader.readAsDataURL(selectedImage);
        });
      }

      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: JSON.stringify({
          claim: claim.trim(),
          image_base64: base64Image
        }),
      });

      if (!response.ok) throw new Error("Server responded with an error");

      const data = await response.json();
      setResult(data);
      setRefreshTrigger(prev => prev + 1);
    } catch (error) {
      alert("Failed to reach OSINT server. Are you running uvicorn main:app on port 8000?");
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = (content, fileName, contentType) => {
    const a = document.createElement("a");
    const file = new Blob([content], { type: contentType });
    a.href = URL.createObjectURL(file);
    a.download = fileName;
    a.click();
  };

  const exportReport = (type) => {
    if (!result) return;
    const content = `OSINT REPORT\nClaim: ${claim}\nVerdict: ${result.verdict}\nConfidence: ${Math.round(result.confidence * 100)}%\n\nExplanation: ${result.explanation}`;

    if (type === 'html') {
      const htmlContent = `<html><body style="font-family:sans-serif; padding:40px;"><h1>OSINT Verification Report</h1><hr/><p><strong>Claim:</strong> ${claim}</p><h2>Verdict: ${result.verdict}</h2><p>${result.explanation}</p></body></html>`;
      downloadFile(htmlContent, 'OSINT_Report.html', 'text/html');
    } else {
      downloadFile(content, 'OSINT_Report.doc', 'application/msword');
    }
  };

  return (
    <div>
      <MetricsBar />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        style={{ flex: 1, padding: '40px 20px' }}
      >
        <div style={{ maxWidth: '1000px', margin: '0 auto' }}>

          <motion.div
            layout
            className="glass-panel"
            style={{ padding: '30px' }}
          >
            {/* Elegant Drag & Drop Zone */}
            <div
              className={`drop-zone ${isDragging ? 'active' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !previewUrl && fileInputRef.current.click()}
            >
              <input
                type="file"
                accept="image/*"
                ref={fileInputRef}
                onChange={handleImageChange}
                style={{ display: 'none' }}
              />

              {previewUrl ? (
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <img
                    src={previewUrl}
                    alt="Preview"
                    style={{ maxHeight: '250px', objectFit: 'contain', borderRadius: '8px', border: '1px solid var(--accent-blue)', boxShadow: '0 10px 30px rgba(0,0,0,0.5)' }}
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); setSelectedImage(null); setPreviewUrl(null); }}
                    style={{ position: 'absolute', top: '10px', right: '10px', background: 'var(--neon-red)', color: 'white', border: 'none', borderRadius: '50%', cursor: 'pointer', padding: '8px 12px', fontSize: '14px', fontWeight: 'bold', boxShadow: '0 0 15px var(--neon-red-glow)', transition: 'transform 0.2s' }}
                    onMouseOver={(e) => e.target.style.transform = 'scale(1.1)'}
                    onMouseOut={(e) => e.target.style.transform = 'scale(1)'}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <div style={{ padding: '40px 20px', pointerEvents: 'none' }}>
                  <div style={{ fontSize: '48px', marginBottom: '15px' }}>📸</div>
                  <h3 className="text-gradient" style={{ margin: '0 0 10px 0', fontSize: '24px' }}>Drag & Drop an image snippet</h3>
                  <p style={{ color: 'var(--text-muted)', margin: 0, fontSize: '16px' }}>or click to browse local files</p>
                </div>
              )}
            </div>

            <textarea
              className="glass-input"
              value={claim}
              onChange={(e) => setClaim(e.target.value)}
              style={{ height: '140px', marginTop: '25px', marginBottom: '25px', resize: 'vertical' }}
              placeholder="Or paste news text, social media quotes, or rumor claims here..."
            />

            <button
              className={`neon-button ${loading ? 'scanning-pulse' : ''}`}
              onClick={handleVerify}
              disabled={loading}
            >
              {loading ? 'PROCESSING GLOBAL OSINT PIPELINE...' : 'Verify'}
            </button>

            <ProgressBar loading={loading} />
          </motion.div>

          <AnimatePresence>
            {result && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -20 }}
                style={{ marginTop: '30px', display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: '25px' }}
              >
                <VerdictCard result={result} />

                <div className="glass-panel" style={{ padding: '25px' }}>
                  <h4 style={{ margin: '0 0 20px 0', color: 'var(--text-secondary)', fontSize: '13px', letterSpacing: '2px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>🌐</span> TOP VERIFICATION SOURCES
                  </h4>
                  {result.sources?.slice(0, 5).map((s, idx) => (
                    <motion.div key={idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.1 }}>
                      <SourceCard source={s} />
                    </motion.div>
                  )) || <p style={{ color: 'var(--text-muted)', fontSize: '14px', fontStyle: 'italic' }}>No external source links found.</p>}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {result && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ display: 'flex', gap: '20px', marginTop: '30px', justifyContent: 'center' }}>
              <button className="neon-button" style={{ width: 'auto', padding: '12px 30px' }} onClick={() => exportReport('html')}>🌐 Export HTML Panel</button>
              <button className="neon-button" style={{ width: 'auto', padding: '12px 30px' }} onClick={() => exportReport('word')}>📄 Export Word Doc</button>
            </motion.div>
          )}

          <motion.div layout style={{ marginTop: '50px' }}>
            <History refreshTrigger={refreshTrigger} />
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}