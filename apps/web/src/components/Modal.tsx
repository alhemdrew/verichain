import React from 'react';

export default function Modal({ title, open, children, onClose }: { title?: string; open: boolean; children: React.ReactNode; onClose?: () => void }) {
  if (!open) return null;
  return (
    <div className="processing-overlay" role="dialog" aria-modal="true">
      <div className="processing-card">
        {title && <h3>{title}</h3>}
        <div>{children}</div>
        <div style={{marginTop:12}}>
          <button className="secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
