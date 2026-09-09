import { useEffect, useMemo, useState } from 'react';
import { apiRequest, getApiBase } from '../../lib/api';
import { useSearch } from '../../lib/search';
import VerificationResult from '../../components/VerificationResult';
import SecurityProcessingAnimation from '../../components/SecurityProcessingAnimation';

type CaseItem = {
  id: number;
  name: string;
  status: string;
};

type EvidenceItem = {
  id: string;
  case_id: number;
  original_filename: string;
  evidence_name?: string | null;
  status?: string;
};

export default function VerificationPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [result, setResult] = useState<{ match: boolean; status: string; verified_at: string; recorded_sha256: string; current_sha256: string; presented_sha256?: string } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [verifyDetails, setVerifyDetails] = useState<any | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const { query } = useSearch();

  const normalizedQuery = query.trim().toLowerCase();
  const filteredEvidence = useMemo(
    () => evidence.filter((item) => {
      if (!normalizedQuery) return true;
      return [item.original_filename, item.evidence_name ?? '', item.status ?? '', item.id]
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery);
    }),
    [evidence, normalizedQuery],
  );

  useEffect(() => {
    async function load() {
      try {
        const caseData = await apiRequest<CaseItem[]>('/cases');
        setCases(caseData);
        const firstCaseId = caseData[0]?.id ?? null;
        setSelectedCaseId(firstCaseId);
        if (firstCaseId !== null) {
          const evidenceData = await apiRequest<EvidenceItem[]>(`/cases/${firstCaseId}/evidence`);
          setEvidence(evidenceData);
          setSelectedEvidenceId(evidenceData[0]?.id ?? null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load evidence');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  useEffect(() => {
    if (selectedCaseId === null) return;
    apiRequest<EvidenceItem[]>(`/cases/${selectedCaseId}/evidence`)
      .then((items) => {
        setEvidence(items);
        if (!selectedEvidenceId && items[0]) setSelectedEvidenceId(items[0].id);
      })
      .catch(() => setEvidence([]));
  }, [selectedCaseId]);

  const selectedEvidence = evidence.find((item) => item.id === selectedEvidenceId) ?? null;

  async function verifySelectedEvidence() {
    if (!selectedEvidence) return;
    setVerifying(true);
    setError('');
    try {
      const verification = await apiRequest<{ match: boolean; status: string; verified_at: string; recorded_sha256: string; current_sha256: string }>(`/evidence/${selectedEvidence.id}/verify`, {
        method: 'POST',
      });
      setResult(verification);
      setVerifyDetails(verification);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setVerifying(false);
    }
  }

  if (loading) return <div className="placeholder-card"><h2>Verification</h2><p>Loading case evidence…</p></div>;

  return (
    <div className="page-shell verification-shell">
      <div className="verification-hero">
        <div className="verification-copy">
          <p className="eyebrow">Verify a presented file</p>
          <h2>Check whether the file in front of you matches the original evidence record.</h2>
          <p className="muted-text">Choose the registered evidence item, compare its fingerprint to the presented file, and confirm a complete chain of custody with cryptographic certainty.</p>
        </div>
        <div className="verification-badges">
          <span>SHA-256</span>
          <span>Chain of custody</span>
        </div>
      </div>

      <div className="verification-grid">
        <div className="drop-panel">
          <div className="drop-box">
            <div className="shield-badge">🛡️</div>
            <h3>Drop file to verify</h3>
            <p>Pick a registered evidence record and compare its exact fingerprint to the file you have in hand.</p>

            {selectedEvidence ? (
              <div className="verification-selector">
                <label htmlFor="verificationEvidenceSelect">Registered evidence</label>
                <select
                  id="verificationEvidenceSelect"
                  value={selectedEvidenceId ?? ''}
                  onChange={(event) => setSelectedEvidenceId(event.target.value || null)}
                >
                  {evidence.map((item) => (
                    <option key={item.id} value={item.id}>{item.evidence_name || item.original_filename}</option>
                  ))}
                </select>
              </div>
            ) : (
              <p className="muted-text" style={{ marginTop: 12 }}>No evidence is available in the selected case.</p>
            )}

            <input aria-label="verify-file-input" type="file" id="verifyInput" style={{display:'none'}} onChange={async (e) => {
              const f = e.target.files ? e.target.files[0] : null;
              if (!f || !selectedEvidence) {
                setError(selectedEvidence ? '' : 'Select a registered evidence item before comparing a file.');
                return;
              }
              setVerifying(true);
              try {
                  setVerifyDetails(null);
                  const form = new FormData();
                  form.append('file', f, f.name);
                  const json = await apiRequest<any>(`/evidence/${selectedEvidence.id}/compare`, { method: 'POST', body: form });
                  setResult({
                    match: Boolean(json.match),
                    status: json.status,
                    verified_at: new Date().toISOString(),
                    recorded_sha256: json.recorded_sha256,
                    current_sha256: json.presented_sha256,
                    presented_sha256: json.presented_sha256,
                  });
                setError('');
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Verification failed');
              } finally {
                setVerifying(false);
              }
            }} />
            <div style={{ marginTop: 18 }}>
              <button className="primary-cta" disabled={!selectedEvidence} onClick={() => document.getElementById('verifyInput')?.click()}>Select file to verify</button>
            </div>
          </div>
        </div>

        <div className="verification-side">
          <div className="metric-card success">
            <span className="metric-label">Evidence chain</span>
            <strong>{evidence.length}</strong>
            <small>registered items available</small>
          </div>

          <div className="metric-card warning">
            <span className="metric-label">Status</span>
            <strong>{result ? (result.match ? 'Verified' : 'Mismatch') : 'Awaiting'}</strong>
            <small>{result ? 'Last comparison completed' : 'No comparison yet'}</small>
          </div>

          {error && <div className="auth-error">{error}</div>}

          {verifying && (
            <div className="processing-card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <SecurityProcessingAnimation size={48} state="processing" />
                <div>
                  <h4>Verifying evidence</h4>
                  <p className="muted-text">Comparing cryptographic fingerprints…</p>
                </div>
              </div>
            </div>
          )}

          {result && (
            <div className={`verification-result ${result.match ? 'verified' : 'failed'}`}>
              <div className="vr-icon" style={{ background: result.match ? 'rgba(46, 207, 154, 0.12)' : 'rgba(255, 107, 125, 0.12)', color: result.match ? '#a8f0d4' : '#ffced4', fontSize: '1.7rem' }}>
                {result.match ? '✓' : '✕'}
              </div>
              <div className="vr-body">
                <div className="vr-title">{result.match ? 'Integrity verified' : 'Integrity mismatch'}</div>
                <div className="vr-msg">{result.match ? 'The presented file matches the registered evidence record.' : 'The presented file does not match the registered evidence fingerprint.'}</div>
                <div className="vr-meta">
                  <div>
                    <label>Registered SHA-256</label>
                    <span>{result.recorded_sha256}</span>
                  </div>
                  <div>
                    <label>Presented SHA-256</label>
                    <span>{result.current_sha256 ?? result.presented_sha256}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
