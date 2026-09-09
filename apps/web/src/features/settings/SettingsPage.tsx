import { useState } from 'react';

export default function SettingsPage() {
  return (
    <div className="placeholder-card" style={{ maxWidth: '900px' }}>
      <div className="page-header-row">
        <div>
          <p className="eyebrow">System settings</p>
          <h2>Platform controls</h2>
        </div>
      </div>

      <div className="settings-panel">
        <div className="settings-item">
          <strong>Investigator profile</strong>
          <small>View and edit your Investigator handle shown across the workspace.</small>
          <ProfileEditor />
        </div>

        <div className="settings-item">
          <strong>Account</strong>
          <small>Manage organization membership and current login session.</small>
          <button type="button" className="secondary">Refresh session</button>
        </div>

        <div className="settings-item">
          <strong>Evidence retention</strong>
          <small>Review how sealed evidence and local vault records are held.</small>
          <button type="button" className="secondary">Open retention schedule</button>
        </div>

        <div className="settings-item">
          <strong>Synchronization</strong>
          <small>Check queue status for authenticated evidence uploads and backups.</small>
          <button type="button" className="secondary">Sync status</button>
        </div>
      </div>
    </div>
  );
}

function ProfileEditor() {
  const [handle, setHandle] = useState(localStorage.getItem('verichain_user_handle') ?? '');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  async function save() {
    setSaving(true);
    setMessage('');
    try {
      const token = localStorage.getItem('verichain_token');
      const res = await fetch((import.meta as any).env?.VITE_API_BASE + '/users/me', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ handle }),
      });
      if (!res.ok) throw new Error('Failed to save profile');
      const data = await res.json();
      localStorage.setItem('verichain_user_handle', data.handle ?? '');
      setMessage('Saved');
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ marginTop: 8 }}>
      <input value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="Investigator handle (e.g., Investigator Rambo)" />
      <button type="button" onClick={save} disabled={saving} style={{ marginLeft: 8 }}>{saving ? 'Saving…' : 'Save'}</button>
      {message && <div style={{ marginTop: 6 }}>{message}</div>}
    </div>
  );
}
