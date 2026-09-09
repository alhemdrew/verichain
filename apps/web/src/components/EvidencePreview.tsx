import React, { useEffect, useState } from 'react';

type Props = {
  evidence: any; // lightweight typing to keep patch small
  apiBase: string;
};

export default function EvidencePreview({ evidence, apiBase }: Props) {
  const [fullscreen, setFullscreen] = useState(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    if (!evidence) return;
    const token = localStorage.getItem('verichain_token');
    const url = `${apiBase}/evidence/${evidence.id}/file`;
    (async () => {
      try {
        const res = await fetch(url, { headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
        if (!mounted || !res.ok) return;
        const blob = await res.blob();
        const u = URL.createObjectURL(blob);
        setBlobUrl(u);
      } catch (err) {
        // ignore preview errors
      }
    })();
    return () => { mounted = false; if (blobUrl) { URL.revokeObjectURL(blobUrl); setBlobUrl(null); } };
  }, [evidence?.id]);

  if (!evidence) return <div className="muted-text">No evidence selected</div>;

  const mime = evidence.mime_type || 'application/octet-stream';

  function handleDownload() {
    if (blobUrl) {
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = evidence.original_filename || 'evidence.bin';
      a.click();
      return;
    }
    const token = localStorage.getItem('verichain_token');
    const link = document.createElement('a');
    link.href = `${apiBase}/evidence/${evidence.id}/file?download=true` + (token ? `&token=${encodeURIComponent(token)}` : '');
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.click();
  }

  if (mime.startsWith('image/')) {
    return (
      <div className="preview image-preview">
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <strong>{evidence.original_filename}</strong>
          <div>
            <button onClick={() => setFullscreen((s) => !s)} className="secondary">{fullscreen ? 'Exit' : 'Fullscreen'}</button>
            <button onClick={handleDownload} className="secondary">Download</button>
          </div>
        </div>
        {blobUrl ? <img src={blobUrl} alt={evidence.original_filename} style={{ width: fullscreen ? '100%' : '100%', maxHeight: fullscreen ? '80vh' : 320, objectFit: 'contain' }} /> : <div className="muted-text">Preview unavailable</div>}
      </div>
    );
  }

  if (mime.startsWith('video/')) {
    return (
      <div className="preview video-preview">
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <strong>{evidence.original_filename}</strong>
          <div>
            <button onClick={handleDownload} className="secondary">Download</button>
          </div>
        </div>
        {blobUrl ? <video controls style={{ width: '100%', maxHeight: 420 }} src={blobUrl} /> : <div className="muted-text">Preview unavailable</div>}
      </div>
    );
  }

  if (mime.startsWith('audio/')) {
    return (
      <div className="preview audio-preview">
        <strong>{evidence.original_filename}</strong>
        {blobUrl ? <audio controls style={{ width: '100%' }} src={blobUrl} /> : <div className="muted-text">Preview unavailable</div>}
        <div style={{marginTop:8}}><button onClick={handleDownload} className="secondary">Download</button></div>
      </div>
    );
  }

  if (mime === 'application/pdf' || mime.startsWith('text/') || evidence.original_filename?.endsWith('.json') || evidence.original_filename?.endsWith('.csv')) {
    return (
      <div className="preview text-pdf-preview">
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <strong>{evidence.original_filename}</strong>
          <div>
            <button onClick={handleDownload} className="secondary">Download</button>
          </div>
        </div>
        {blobUrl ? <iframe src={blobUrl} style={{ width: '100%', height: '480px', border: 'none', marginTop:8 }} title="preview" /> : <div className="muted-text">Preview unavailable</div>}
      </div>
    );
  }

  return (
    <div className="preview file-preview">
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div>
          <strong>{evidence.original_filename}</strong>
          <div className="muted-text">{mime} • {evidence.file_size ?? 'Unknown'}</div>
        </div>
        <div>
          <button onClick={handleDownload} className="secondary">Download</button>
        </div>
      </div>
      <div style={{marginTop:12}} className="file-icon">📦</div>
    </div>
  );
}
