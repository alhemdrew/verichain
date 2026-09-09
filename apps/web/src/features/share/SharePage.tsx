import { useEffect, useMemo, useState } from 'react';
import { apiRequest } from '../../lib/api';
import { useSearch } from '../../lib/search';

type ShareItem = {
  id: string;
  evidence_id: string;
  recipient_user_id: number;
  created_by_user_id: number;
  permissions: string[];
  expires_at: string | null;
  revoked_at: string | null;
  status: string;
};

type EvidenceItem = {
  id: string;
  original_filename: string;
  status: string;
  case_id: number;
};

export default function SharePage() {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [shares, setShares] = useState<ShareItem[]>([]);
  const [recipientUserId, setRecipientUserId] = useState('');
  const [recipientEmail, setRecipientEmail] = useState('');
  const [searchResults, setSearchResults] = useState<{ id: number; name: string; email: string; organization_id: number }[]>([]);
  const [sharePermissions, setSharePermissions] = useState<string[]>(['VIEW']);
  const [expiresAt, setExpiresAt] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const { query } = useSearch();

  const normalizedQuery = query.trim().toLowerCase();
  const filteredEvidence = useMemo(
    () => evidence.filter((item) => {
      if (!normalizedQuery) return true;
      return [item.original_filename, item.status, String(item.case_id), item.id].join(' ').toLowerCase().includes(normalizedQuery);
    }),
    [evidence, normalizedQuery],
  );

  useEffect(() => {
    async function load() {
      try {
        const caseData = await apiRequest<{ id: number; name: string; status: string }[]>('/cases');
        const allEvidence: EvidenceItem[] = [];
        for (const item of caseData) {
          const caseEvidence = await apiRequest<EvidenceItem[]>(`/cases/${item.id}/evidence`);
          allEvidence.push(...caseEvidence);
        }
        setEvidence(allEvidence);
        setSelectedEvidenceId(allEvidence[0]?.id ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load shared evidence');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  useEffect(() => {
    if (!selectedEvidenceId) return;
    apiRequest<ShareItem[]>(`/evidence/${selectedEvidenceId}/shares`)
      .then(setShares)
      .catch(() => setShares([]));
  }, [selectedEvidenceId]);

  const selectedEvidence = evidence.find((item) => item.id === selectedEvidenceId) ?? null;

  async function createShare() {
    if (!selectedEvidence || !recipientUserId.trim()) {
      setError('Select evidence and choose a recipient user');
      return;
    }

    try {
      await apiRequest(`/evidence/${selectedEvidence.id}/shares`, {
        method: 'POST',
        body: JSON.stringify({
          recipient_user_id: Number(recipientUserId),
          permissions: sharePermissions,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        }),
      });
      const refreshed = await apiRequest<ShareItem[]>(`/evidence/${selectedEvidence.id}/shares`);
      setShares(refreshed);
      setRecipientUserId('');
      setSharePermissions(['VIEW']);
      setExpiresAt('');
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Share creation failed');
    }
  }

  async function lookupUserByEmail() {
    if (!recipientEmail.trim()) return;
    try {
      setError('');
      const results = await apiRequest<any[]>(`/users/search?email=${encodeURIComponent(recipientEmail.trim())}`);
      setSearchResults(results || []);
      if ((results || []).length === 0) {
        setError('No matching user found in your organization');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lookup failed');
    }
  }

  async function revokeShare(shareId: string) {
    try {
      await apiRequest(`/shares/${shareId}/revoke`, { method: 'POST' });
      const refreshed = await apiRequest<ShareItem[]>(`/evidence/${selectedEvidence!.id}/shares`);
      setShares(refreshed);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Share revocation failed');
    }
  }

  if (loading) return <div className="placeholder-card"><h2>Sharing</h2><p>Loading shareable evidence…</p></div>;

  return (
    <div className="placeholder-card" style={{ maxWidth: '1100px' }}>
      <div className="page-header-row">
        <div>
          <p className="eyebrow">Permissioned access</p>
          <h2>Evidence sharing</h2>
        </div>
      </div>

      {error && <div className="auth-error">{error}</div>}

      <div className="evidence-layout">
        <div className="evidence-list">
          {filteredEvidence.length === 0 ? (
            <p className="muted-text">{normalizedQuery ? 'No evidence matches the current search.' : 'No evidence available to share.'}</p>
          ) : (
            filteredEvidence.map((item) => (
              <button key={item.id} type="button" className={`evidence-item ${selectedEvidenceId === item.id ? 'selected' : ''}`} onClick={() => setSelectedEvidenceId(item.id)}>
                <strong>{item.original_filename}</strong>
                <span>{item.status}</span>
                <small>Case {item.case_id}</small>
              </button>
            ))
          )}
        </div>

        <div className="evidence-detail">
          {selectedEvidence ? (
            <>
              <div className="crypto-header">
                <div>
                  <p className="eyebrow">Selected evidence</p>
                  <h3>{selectedEvidence.original_filename}</h3>
                </div>
              </div>

              <div className="verification-panel">
                <h4>Share this evidence</h4>
                <div className="share-form-row">
                  <input type="email" value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)} placeholder="Recipient email (person@example.com)" />
                  <button type="button" onClick={lookupUserByEmail}>Lookup</button>
                  <div style={{ width: '100%', marginTop: 8 }}>
                    {searchResults.length > 0 ? (
                      <div>
                        {searchResults.map((u) => (
                          <div key={u.id} style={{ padding: 6, border: '1px solid #eee', marginBottom: 6 }}>
                            <div><strong>{u.name}</strong></div>
                            <div>{u.email}</div>
                            <div style={{ marginTop: 6 }}>
                              <button type="button" onClick={() => { setRecipientUserId(String(u.id)); setRecipientEmail(u.email); setSearchResults([]); setError(''); }}>Select</button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ marginTop: 8 }}>
                        <small>Or enter recipient user ID manually</small>
                        <input type="number" value={recipientUserId} onChange={(event) => setRecipientUserId(event.target.value)} placeholder="Recipient user ID" />
                      </div>
                    )}
                  </div>

                  <div className="permission-toggle-row">
                    {['VIEW', 'DOWNLOAD'].map((permission) => (
                      <label key={permission}>
                        <input type="checkbox" checked={sharePermissions.includes(permission)} onChange={() => setSharePermissions((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission])} />
                        {permission}
                      </label>
                    ))}
                  </div>
                  <input type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} />
                  <button type="button" onClick={createShare}>Create share</button>
                </div>
              </div>

              <div className="verification-panel">
                <h4>Active shares</h4>
                {shares.length === 0 ? <p className="muted-text">No active shares for this evidence.</p> : (
                  <div className="share-list">
                    {shares.map((share) => (
                      <div key={share.id} className="share-row">
                        <div>
                          <strong>Recipient {share.recipient_user_id}</strong>
                          <div>{share.permissions.join(', ')}</div>
                          <small>{share.status} • {share.expires_at ?? 'No expiration'}</small>
                        </div>
                        <button type="button" className="secondary" onClick={() => revokeShare(share.id)}>Revoke</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="muted-text">Choose evidence to create or inspect a share.</p>
          )}
        </div>
      </div>
    </div>
  );
}
