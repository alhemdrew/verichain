import React from 'react';

type Props = {
  state: 'verified' | 'failed' | 'pending' | 'error' | 'unavailable';
  title?: string;
  message?: string;
  timestamp?: string;
  details?: Array<{ label: string; value: string }>; // technical details
};

export default function VerificationResult({ state, title, message, timestamp, details = [] }: Props) {
  const cls = `verification-result ${state === 'verified' ? 'verified' : state === 'failed' ? 'failed' : 'pending'}`;
  const icon = state === 'verified' ? '✓' : state === 'failed' ? '⚠' : state === 'pending' ? '…' : '⏸';
  return (
    <div className={cls} role="status">
      <div className="vr-icon">{icon}</div>
      <div className="vr-body">
        <div className="vr-title">{title || (state === 'verified' ? 'Integrity Verified' : state === 'failed' ? 'Integrity Check Failed' : 'Verification Pending')}</div>
        {message && <div className="vr-msg">{message}</div>}
        {timestamp && <div className="vr-meta">{timestamp}</div>}
        {details.length > 0 && (
          <details style={{ marginTop: 10 }}>
            <summary style={{ cursor: 'pointer', color: 'var(--muted)' }}>Technical Details ▾</summary>
            <div style={{ marginTop: 8 }}>
              {details.map((d) => (
                <div key={d.label} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                  <div style={{ color: 'var(--muted)', minWidth: 140, fontWeight: 700, fontSize: '0.78rem' }}>{d.label}</div>
                  <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace', color: 'var(--text)' }}>{d.value}</div>
                </div>
              ))}
            </div>
          </details>
        )}
        <div className="vr-actions">
          <button className="btn-ghost">View Verification Report</button>
          <button className="btn-ghost">Copy Hash</button>
        </div>
      </div>
    </div>
  );
}
