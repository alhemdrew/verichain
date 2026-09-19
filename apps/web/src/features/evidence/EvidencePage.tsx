import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useSearch } from '../../lib/search';
import EvidencePreview from '../../components/EvidencePreview';
import ActionMenu from '../../components/ActionMenu';
import Modal from '../../components/Modal';
import VerificationResult from '../../components/VerificationResult';
import SecurityProcessingAnimation from '../../components/SecurityProcessingAnimation';

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

type CaseItem = {
  id: number;
  name: string;
  status: string;
  organization_id: number;
};

type EvidenceItem = {
  id: string;
  case_id: number;
  organization_id: number;
  original_filename: string;
  evidence_name?: string | null;
  evidence_type: string;
  mime_type: string | null;
  file_size: number;
  description: string | null;
  status: string;
  storage_reference: string | null;
  sha256: string | null;
  original_sha256: string | null;
  manifest_sha256: string | null;
  sealed_at: string | null;
  seal_version: string | null;
  vault_status: string | null;
  vault_algorithm: string | null;
  vault_version: string | null;
  vault_path: string | null;
  vault_object_id: string | null;
  signature: string | null;
  signature_algorithm: string | null;
  key_id: string | null;
  signature_version: string | null;
  signed_at: string | null;
};

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

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem('verichain_token');
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail ?? `Request failed (${response.status})`);
    }
    return data as T;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('OFFLINE');
    }
    throw error;
  }
}

export default function EvidencePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<number | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState('');
  const [actionNotice, setActionNotice] = useState('');
  const [offlineMode, setOfflineMode] = useState(false);
  const [verification, setVerification] = useState<{ match: boolean; recorded_sha256: string; current_sha256: string; verified_at: string; status: string } | null>(null);
  const [signatureVerification, setSignatureVerification] = useState<{ signature_valid: boolean; overall_valid: boolean; evidence_integrity: boolean; manifest_integrity: boolean; key_id: string | null; signature_algorithm: string | null; signature_version: string | null; status: string; verified_at: string } | null>(null);
  const [vaultStatus, setVaultStatus] = useState<{ vault_status: string; vault_object_id: string | null; status: string; original_sha256: string; vault_path: string | null } | null>(null);
  const [report, setReport] = useState<{ evidence_id: string; verification_status: string; sha256_status: string; manifest_status: string; signature_status: string; custody_status: string; generated_at: string } | null>(null);
  const [newOriginalFilename, setNewOriginalFilename] = useState('');
  const [newEvidenceName, setNewEvidenceName] = useState('');
  const [newEvidenceType, setNewEvidenceType] = useState('BINARY');
  const [newEvidenceMimeType, setNewEvidenceMimeType] = useState('application/octet-stream');
  const [newEvidenceDescription, setNewEvidenceDescription] = useState('');
  const [newEvidenceFile, setNewEvidenceFile] = useState<File | null>(null);
  const [processingPhase, setProcessingPhase] = useState<string | null>(null);
  const [processingPct, setProcessingPct] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<number | null>(null);
  const [isSealing, setIsSealing] = useState(false);
  const [sharePermissions, setSharePermissions] = useState<string[]>(['VIEW']);
  const [recipientUserId, setRecipientUserId] = useState<string>('');
  const [recipientEmail, setRecipientEmail] = useState<string>('');
  const [foundRecipient, setFoundRecipient] = useState<{ id: number; name: string; email: string } | null>(null);
  const [shareExpiresAt, setShareExpiresAt] = useState<string>('');
  const [shares, setShares] = useState<ShareItem[]>([]);
  const [isSharing, setIsSharing] = useState(false);
  const [presentedFile, setPresentedFile] = useState<File | null>(null);
  const [presentedResult, setPresentedResult] = useState<{ presented_filename?: string | null; presented_sha256?: string | null; recorded_sha256?: string | null; match?: boolean; status?: string } | null>(null);
  const [custodyEvents, setCustodyEvents] = useState<any[]>([]);
  const { query, setQuery } = useSearch();

  const normalizedQuery = query.trim().toLowerCase();
  const filteredEvidence = useMemo(
    () => evidence.filter((item) => {
      if (!normalizedQuery) return true;
      return [item.original_filename, item.evidence_name ?? '', item.evidence_type, item.status, (item.description ?? '')]
        .join(' ')
        .toLowerCase()
        .includes(normalizedQuery);
    }),
    [evidence, normalizedQuery],
  );

  const selectedEvidence = useMemo(
    () => evidence.find((item) => item.id === selectedEvidenceId) ?? null,
    [evidence, selectedEvidenceId],
  );

  useEffect(() => {
    async function load() {
      try {
        const casesData = await requestJson<CaseItem[]>('/cases');
        setCases(casesData);
        const firstCaseId = casesData[0]?.id ?? null;
        setSelectedCaseId(firstCaseId);
        if (firstCaseId !== null) {
          const evidenceData = await requestJson<EvidenceItem[]>(`/cases/${firstCaseId}/evidence`);
          setEvidence(evidenceData);
          setSelectedEvidenceId(evidenceData[0]?.id ?? null);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load evidence';
        setOfflineMode(message === 'OFFLINE');
        setActionError(message === 'OFFLINE' ? 'OFFLINE MODE: Evidence can still be collected securely.' : message);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  useEffect(() => {
    if (selectedCaseId === null) return;
    async function loadEvidence() {
      try {
        const evidenceData = await requestJson<EvidenceItem[]>(`/cases/${selectedCaseId}/evidence`);
        setEvidence(evidenceData);
        setSelectedEvidenceId((current) => current ?? evidenceData[0]?.id ?? null);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load evidence';
        setOfflineMode(message === 'OFFLINE');
        setActionError(message === 'OFFLINE' ? 'OFFLINE MODE: Evidence can still be collected securely.' : message);
      }
    }

    loadEvidence();
  }, [selectedCaseId]);

  useEffect(() => {
    if (!selectedEvidence) return;
    const selectedEvidenceIdValue = selectedEvidence.id;

    async function loadShares() {
      try {
        const result = await requestJson<ShareItem[]>(`/evidence/${selectedEvidenceIdValue}/shares`);
        setShares(result);
      } catch (error) {
        setShares([]);
      }
    }
    async function loadCustody() {
      try {
        const res = await requestJson<any[]>(`/evidence/${selectedEvidenceIdValue}/custody`);
        setCustodyEvents(res);
      } catch (err) {
        setCustodyEvents([]);
      }
    }
    loadShares();
    loadCustody();
  }, [selectedEvidence]);

  async function handleCreateEvidence() {
    if (!selectedCaseId) return null;
    const safeOriginalName = newOriginalFilename.trim() || 'uploaded-evidence.bin';
    const safeEvidenceName = newEvidenceName.trim() || safeOriginalName;

    try {
      setActionError('');

      if (newEvidenceFile) {
        const token = localStorage.getItem('verichain_token');
        const form = new FormData();
        form.append('file', newEvidenceFile, safeOriginalName);
        const created = await fetch(`${API_BASE}/cases/${selectedCaseId}/evidence/upload`, {
          method: 'POST',
          body: form,
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });

        const data = await created.json().catch(() => null);
        if (!created.ok) {
          throw new Error(data?.detail || 'Evidence upload failed');
        }

        const updated = await requestJson<EvidenceItem>(`/evidence/${data.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            evidence_name: safeEvidenceName,
            description: newEvidenceDescription || 'Digital evidence preserved for integrity verification.',
            mime_type: newEvidenceMimeType || newEvidenceFile.type || 'application/octet-stream',
            evidence_type: newEvidenceType.toUpperCase(),
          }),
        });

        setEvidence((current) => [updated, ...current.filter((item) => item.id !== updated.id)]);
        setSelectedEvidenceId(updated.id);
        setNewOriginalFilename('verichain-demo-evidence.txt');
        setNewEvidenceName('VeriChain demonstration evidence');
        setNewEvidenceType('TEXT');
        setNewEvidenceMimeType('text/plain');
        setNewEvidenceDescription('VERICHAIN DEMONSTRATION EVIDENCE\nCase: RCN-DEMO-001\nPurpose: Integrity lifecycle validation');
        setNewEvidenceFile(null);
        setVerification(null);
        setSignatureVerification(null);
        setVaultStatus(null);
        setReport(null);
        return updated;
      }

      const text = `Evidence captured for case ${selectedCaseId} on ${new Date().toISOString()}`;
      const payload = {
        original_filename: safeOriginalName,
        evidence_name: safeEvidenceName,
        evidence_type: newEvidenceType.toUpperCase(),
        mime_type: newEvidenceMimeType || 'application/octet-stream',
        file_size: text.length,
        description: newEvidenceDescription || 'Digital evidence preserved for integrity verification.',
        content_base64: window.btoa(text),
      };

      const created = await requestJson<EvidenceItem>(`/cases/${selectedCaseId}/evidence`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setEvidence((current) => [created, ...current]);
      setSelectedEvidenceId(created.id);
      setNewOriginalFilename('verichain-demo-evidence.txt');
      setNewEvidenceName('VeriChain demonstration evidence');
      setNewEvidenceType('TEXT');
      setNewEvidenceMimeType('text/plain');
      setNewEvidenceDescription('VERICHAIN DEMONSTRATION EVIDENCE\nCase: RCN-DEMO-001\nPurpose: Integrity lifecycle validation');
      setNewEvidenceFile(null);
      setVerification(null);
      setSignatureVerification(null);
      setVaultStatus(null);
      setReport(null);
      return created;
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Evidence creation failed');
      return null;
    }
  }

  async function sealEvidenceById(evidenceId: string) {
    try {
      const result = await requestJson<{ evidence_id: string; sha256: string; manifest_sha256: string; sealed_at: string; seal_version: string; status: string }>(`/evidence/${evidenceId}/seal`, {
        method: 'POST',
      });
      setEvidence((current) => current.map((item) => item.id === evidenceId ? { ...item, sha256: result.sha256, manifest_sha256: result.manifest_sha256, sealed_at: result.sealed_at, seal_version: result.seal_version, status: result.status, original_sha256: result.sha256 } : item));
      setVerification(null);
      return result;
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Sealing failed');
      return null;
    }
  }

  async function verifyEvidenceById(evidenceId: string) {
    try {
      const result = await requestJson<{ match: boolean; recorded_sha256: string; current_sha256: string; verified_at: string; status: string }>(`/evidence/${evidenceId}/verify`, {
        method: 'POST',
      });
      setVerification(result);
      return result;
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Verification failed');
      return null;
    }
  }

  async function handleSeal() {
    if (!selectedEvidence) return;
    await sealEvidenceById(selectedEvidence.id);
  }

  async function handleVerify() {
    if (!selectedEvidence) return;
    await verifyEvidenceById(selectedEvidence.id);
  }

  async function handleSign() {
    if (!selectedEvidence) return;
    setActionError('');
    try {
      const result = await requestJson<{ evidence_id: string; signature_valid: boolean; signature_algorithm: string | null; key_id: string | null; signature_version: string | null; signed_at: string | null; public_key_pem: string | null; status: string }>(`/evidence/${selectedEvidence.id}/sign`, {
        method: 'POST',
      });
      setSignatureVerification({
        signature_valid: result.signature_valid,
        overall_valid: result.signature_valid,
        evidence_integrity: true,
        manifest_integrity: true,
        key_id: result.key_id,
        signature_algorithm: result.signature_algorithm,
        signature_version: result.signature_version,
        status: result.status,
        verified_at: result.signed_at ?? new Date().toISOString(),
      });
      setEvidence((current) => current.map((item) => item.id === selectedEvidence.id ? { ...item, signature: result.evidence_id ? 'stored' : null, signature_algorithm: result.signature_algorithm, key_id: result.key_id, signature_version: result.signature_version, signed_at: result.signed_at } : item));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Signing failed');
    }
  }

  async function handleVerifySignature() {
    if (!selectedEvidence) return;
    setActionError('');
    try {
      const result = await requestJson<{ evidence_id: string; evidence_integrity: boolean; manifest_integrity: boolean; signature_valid: boolean; custody_chain_valid: boolean; overall_valid: boolean; key_id: string | null; signature_algorithm: string | null; signature_version: string | null; status: string; verified_at: string }>(`/evidence/${selectedEvidence.id}/verify-signature`, {
        method: 'POST',
      });
      setSignatureVerification(result);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Signature verification failed');
    }
  }

  async function handleStoreVault() {
    if (!selectedEvidence) return;
    setActionError('');
    try {
      const result = await requestJson<{ evidence_id: string; vault_object_id: string; vault_path: string; vault_status: string; original_sha256: string; status: string }>(`/evidence/${selectedEvidence.id}/vault/store`, {
        method: 'POST',
      });
      setVaultStatus(result);
      setEvidence((current) => current.map((item) => item.id === selectedEvidence.id ? { ...item, vault_status: result.vault_status, vault_path: result.vault_path, vault_object_id: result.vault_object_id, vault_algorithm: 'AES-256-GCM', vault_version: 'aesgcm-v1' } : item));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Vault storage failed');
    }
  }

  async function handleCreateDerivative() {
    if (!selectedEvidence) return;
    setActionError('');
    try {
      const result = await requestJson<{ derivative_evidence_id: string; parent_evidence_id: string; derivation_type: string; description: string | null; sha256: string; manifest_sha256: string; status: string }>(`/evidence/${selectedEvidence.id}/derivatives`, {
        method: 'POST',
        body: JSON.stringify({ derivation_type: 'COPY', description: 'Demonstration derivative created during live verification' }),
      });
      setActionError(`Derivative created: ${result.derivative_evidence_id}`);
      setEvidence((current) => current.some((item) => item.id === result.derivative_evidence_id)
        ? current
        : [{ ...current[0], id: result.derivative_evidence_id, original_filename: `${selectedEvidence.original_filename}-derivative`, status: result.status, sha256: result.sha256, manifest_sha256: result.manifest_sha256 }, ...current]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Derivative creation failed');
    }
  }

  async function handleLoadReport() {
    if (!selectedEvidence) return;
    try {
      const result = await requestJson<{ evidence_id: string; verification_status: string; sha256_status: string; manifest_status: string; signature_status: string; custody_status: string; generated_at: string }>(`/evidence/${selectedEvidence.id}/report`);
      setReport(result);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Report generation failed');
    }
  }

  async function handleDownloadReportPdf(mode: 'summary' | 'detailed' = 'summary') {
    if (!selectedEvidence) return;
    setActionError('');
    setIsDownloading(true);
    setDownloadProgress(0);

    try {
      const token = localStorage.getItem('verichain_token');
      // add timestamp cache-buster to ensure we don't get a cached PDF
      const urlFetch = `${API_BASE}/evidence/${selectedEvidence.id}/report.pdf?mode=${mode}&_ts=${Date.now()}`;
      const res = await fetch(urlFetch, {
        method: 'GET',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (!res.ok) throw new Error('Failed to fetch PDF');

      // Try to detect filename from Content-Disposition
      const disposition = res.headers.get('Content-Disposition') || '';
      let filename = `${selectedEvidence.original_filename || 'verichain-report'}-${mode}.pdf`;
      const match = /filename="(?<name>[^"]+)"/.exec(disposition);
      if (match && match.groups && match.groups.name) {
        filename = match.groups.name;
      }

      // Stream the response to track progress when Content-Length is present
      const contentLength = Number(res.headers.get('Content-Length') || res.headers.get('content-length') || 0) || null;
      if (res.body && typeof res.body.getReader === 'function') {
        const reader = res.body.getReader();
        const chunks: Uint8Array[] = [];
        let received = 0;
        // Read loop
        // eslint-disable-next-line no-constant-condition
        while (true) {
          // eslint-disable-next-line no-await-in-loop
          const { done, value } = await reader.read();
          if (done) break;
          if (value) {
            chunks.push(value);
            received += value.length;
            if (contentLength) {
              setDownloadProgress(Math.round((received / contentLength) * 100));
            }
          }
        }
        const blob = new Blob(
          chunks.map((chunk) => chunk.buffer.slice(chunk.byteOffset, chunk.byteOffset + chunk.byteLength) as ArrayBuffer),
          { type: 'application/pdf' },
        );
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 15000);
      } else {
        // Fallback: blob
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 15000);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'PDF download failed');
    }
    finally {
      setIsDownloading(false);
      setDownloadProgress(null);
    }
  }

  async function handleVerifyPresentedFile() {
    if (!selectedEvidence || !presentedFile) return;
    setActionError('');
    setPresentedResult(null);
    try {
      const token = localStorage.getItem('verichain_token');
      const fd = new FormData();
      fd.append('file', presentedFile, presentedFile.name);
      const res = await fetch(`${API_BASE}/evidence/${selectedEvidence.id}/compare`, {
        method: 'POST',
        body: fd,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Presented file verification failed');
      }
      const body = await res.json();
      setPresentedResult(body);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Presented file verification failed');
    }
  }

  async function handleCreateShare() {
    if (!selectedEvidence || !foundRecipient) return;
    setActionError('');
    setActionNotice('');
    try {
      setIsSharing(true);
      const created = await requestJson<ShareItem>(`/evidence/${selectedEvidence.id}/shares`, {
        method: 'POST',
        body: JSON.stringify({
          recipient_user_id: Number(foundRecipient.id),
          permissions: sharePermissions,
          expires_at: shareExpiresAt ? new Date(shareExpiresAt).toISOString() : null,
        }),
      });
      await requestJson(`/shares/${created.id}/send-email`, { method: 'POST' });
      const refreshed = await requestJson<ShareItem[]>(`/evidence/${selectedEvidence.id}/shares`);
      setShares(refreshed);
      setRecipientUserId('');
      setRecipientEmail('');
      setFoundRecipient(null);
      setSharePermissions(['VIEW']);
      setShareExpiresAt('');
      setActionNotice(`Share created and email sent to ${foundRecipient.email}.`);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Share creation or email delivery failed');
    } finally {
      setIsSharing(false);
    }
  }

  async function handleLookupByEmail() {
    if (!recipientEmail.trim()) return;
    setActionError('');
    try {
      const results = await requestJson<any[]>(`/users/search?email=${encodeURIComponent(recipientEmail.trim())}`);
      if (results.length === 0) {
        setFoundRecipient(null);
        setActionError('No account found for that email');
        return;
      }
      const u = results[0];
      setFoundRecipient({ id: u.id, name: u.name, email: u.email });
      setRecipientUserId(String(u.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Lookup failed');
    }
  }

  async function handleRevokeShare(shareId: string) {
    try {
      await requestJson<{ share_id: string; status: string; revoked_at: string | null }>(`/shares/${shareId}/revoke`, {
        method: 'POST',
      });
      const refreshed = await requestJson<ShareItem[]>(`/evidence/${selectedEvidence!.id}/shares`);
      setShares(refreshed);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Revocation failed');
    }
  }

  if (loading) {
    return <div className="placeholder-card"><h2>Evidence</h2><p>Loading evidence workspace…</p></div>;
  }

  return (
    <div className="evidence-shell">
      {processingPhase && (
        <div className="processing-overlay" role="status" aria-live="polite">
          <div className="processing-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <SecurityProcessingAnimation size={56} state={processingPct >= 100 ? 'success' : 'processing'} />
              <div>
                <h3>{processingPhase}</h3>
                <p className="muted-text">{processingPhase === 'Uploading Evidence' ? 'Securing your evidence file…' : processingPhase === 'Generating Cryptographic Fingerprint' ? 'Calculating SHA-256 integrity fingerprint…' : 'Creating canonical record and chain-of-custody…'}</p>
              </div>
            </div>
            <div className="processing-progress"><i style={{ width: `${processingPct}%` }} /></div>
          </div>
        </div>
      )}

      <header className="section-header">
        <div>
          <p className="eyebrow">EVIDENCE</p>
          <h1>Evidence workspace</h1>
          <p className="muted-text">Register, preserve, and verify each item without altering the original.</p>
        </div>
        <div className="header-actions">
          <button type="button" className="primary-cta" onClick={() => window.location.assign('/evidence/register')}>+ REGISTER EVIDENCE</button>
          <button type="button" className="secondary-cta" onClick={() => window.location.assign('/verify/presented')}>VERIFY A PRESENTED FILE</button>
        </div>
      </header>

      <div className="summary-grid">
        <div className="stat-card"><span>Total evidence</span><strong>{evidence.length}</strong></div>
        <div className="stat-card"><span>Verified</span><strong>{evidence.filter((item) => item.status === 'SEALED' || item.status === 'VERIFIED').length}</strong></div>
        <div className="stat-card"><span>Pending</span><strong>{evidence.filter((item) => item.status !== 'SEALED' && item.status !== 'VERIFIED').length}</strong></div>
        <div className="stat-card warning"><span>Integrity issues</span><strong>{evidence.filter((item) => item.status === 'INTEGRITY FAILURE').length}</strong></div>
      </div>

      <div className="evidence-workbench">
        <section className="panel intake-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">NEW EVIDENCE</p>
              <h2>Preserve the original item</h2>
            </div>
            <div className="status-chip neutral">Chain-of-custody active</div>
          </div>

          <div className="drop-zone" onClick={() => document.getElementById('evidence-upload')?.click()}>
            <div className="drop-zone-icon">🛡️</div>
            <strong>Drop evidence here</strong>
            <p>PDF, image, video, audio, or document</p>
            <button type="button" className="primary-cta" onClick={(event) => { event.stopPropagation(); document.getElementById('evidence-upload')?.click(); }}>Choose file</button>
            <input id="evidence-upload" type="file" hidden onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              setNewEvidenceFile(file);
              setNewOriginalFilename(file.name);
              setNewEvidenceName(file.name);
              setNewEvidenceMimeType(file.type || 'application/octet-stream');
              setNewEvidenceType(file.type.includes('image') ? 'IMAGE' : file.type.includes('video') ? 'VIDEO' : file.type.includes('audio') ? 'AUDIO' : 'BINARY');
            }} />
          </div>

          <div className="intake-form">
            <label>
              <span>Case</span>
              <select value={selectedCaseId ?? ''} onChange={(event) => setSelectedCaseId(Number(event.target.value))}>
                {cases.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <div className="identity-block">
              <span>Original filename</span>
              <div className="read-only-field">{newOriginalFilename || 'No file selected'}</div>
            </div>
            <label>
              <span>Evidence name</span>
              <input
                aria-label="evidence-name"
                placeholder="example: Witness A interview recording"
                value={newEvidenceName}
                onChange={(event) => setNewEvidenceName(event.target.value)}
              />
            </label>
            <label>
              <span>Evidence description</span>
              <textarea
                aria-label="evidence-description"
                placeholder="Describe the item, collection context, and why it is relevant to the case."
                value={newEvidenceDescription}
                onChange={(event) => setNewEvidenceDescription(event.target.value)}
                rows={4}
              />
            </label>
            <div className="submit-row">
              <div className="file-summary">
                {newOriginalFilename ? (
                  <>
                    <span className="file-pill">File ready</span>
                    <strong>{newOriginalFilename}</strong>
                  </>
                ) : (
                  <span className="muted-text">No file selected yet.</span>
                )}
              </div>
              <button
                className="primary-cta"
                aria-label="register-evidence"
                type="button"
                onClick={async () => {
                  try {
                    if (!newOriginalFilename.trim()) {
                      setActionError('Choose a file before registering evidence.');
                      return;
                    }
                    setProcessingPhase('Uploading Evidence');
                    setProcessingPct(10);
                    await new Promise((resolve) => setTimeout(resolve, 250));
                    setProcessingPhase('Generating Cryptographic Fingerprint');
                    setProcessingPct(45);
                    await new Promise((resolve) => setTimeout(resolve, 250));
                    const created = await handleCreateEvidence();
                    setProcessingPct(75);
                    await new Promise((resolve) => setTimeout(resolve, 250));
                    setProcessingPhase('Preserving Evidence');
                    setProcessingPct(90);
                    await new Promise((resolve) => setTimeout(resolve, 250));
                    if (created) {
                      await sealEvidenceById(created.id);
                      await verifyEvidenceById(created.id);
                    }
                    setProcessingPct(100);
                    setTimeout(() => {
                      setProcessingPhase(null);
                      setProcessingPct(0);
                    }, 700);
                  } catch (err) {
                    setProcessingPhase(null);
                    setProcessingPct(0);
                    setActionError(err instanceof Error ? err.message : 'Registration failed');
                  }
                }}
              >
                Register evidence
              </button>
            </div>
          </div>
        </section>

        <aside className="panel list-panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">REGISTERED</p>
              <h2>Evidence list</h2>
            </div>
          </div>

          <div className="toolbar-search compact">
            <span>⌕</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search evidence…" aria-label="Search evidence" />
          </div>

          <div className="evidence-list">
            {filteredEvidence.length === 0 ? (
              <div className="empty-list muted-text">{normalizedQuery ? 'No evidence matches the current search.' : 'No evidence in this case yet.'}</div>
            ) : (
              filteredEvidence.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`evidence-item ${selectedEvidenceId === item.id ? 'selected' : ''}`}
                  onClick={() => {
                    setSelectedEvidenceId(item.id);
                    setVerification(null);
                  }}
                >
                  <div>
                    <strong>{item.evidence_name || item.original_filename}</strong>
                    <small>{item.original_filename}</small>
                  </div>
                  <span className={`status-badge ${item.status === 'SEALED' || item.status === 'VERIFIED' ? 'verified' : item.status === 'INTEGRITY FAILURE' ? 'failed' : 'pending'}`}>
                    {item.status === 'SEALED' || item.status === 'VERIFIED' ? 'VERIFIED' : item.status === 'INTEGRITY FAILURE' ? 'FAILURE' : 'PENDING'}
                  </span>
                </button>
              ))
            )}
          </div>
        </aside>
      </div>

      {offlineMode && (
        <div className="auth-error" style={{ background: '#fff5d6', color: '#5e4300', borderColor: '#f2c94c' }}>
          OFFLINE MODE — Evidence can still be collected securely.
        </div>
      )}

      {actionError && !offlineMode && <div className="auth-error">{actionError}</div>}
      {actionNotice && <div className="success-banner" role="status">{actionNotice}</div>}

      {selectedEvidence && (
        <section className="panel detail-panel">
          <div className="detail-header">
            <div>
              <p className="eyebrow">SELECTED ITEM</p>
              <h2>{selectedEvidence.evidence_name || selectedEvidence.original_filename}</h2>
              <p className="muted-text">Original filename: {selectedEvidence.original_filename}</p>
            </div>
            <div className="detail-actions">
              <button type="button" className="primary-cta" onClick={handleVerify} disabled={isDownloading || isSealing}>Verify integrity</button>
              <button type="button" className="secondary-cta" onClick={handleLoadReport} disabled={isDownloading || isSealing}>Load report</button>
              <button
                type="button"
                className="secondary-cta"
                onClick={() => handleDownloadReportPdf('summary')}
                disabled={isDownloading || isSealing}
              >
                {isDownloading && downloadProgress !== null ? `Downloading (${downloadProgress}%)` : isDownloading ? 'Downloading…' : 'Download summary PDF'}
              </button>
              <button
                type="button"
                className="secondary-cta"
                onClick={() => handleDownloadReportPdf('detailed')}
                disabled={isDownloading || isSealing}
              >
                {isDownloading && downloadProgress !== null ? `Downloading (${downloadProgress}%)` : isDownloading ? 'Downloading…' : 'Download detailed PDF'}
              </button>
              <button type="button" className="secondary-cta" onClick={() => window.location.assign('/verify/presented')} disabled={isDownloading || isSealing}>Verify presented file</button>
              {/* Seal action - visible when evidence not sealed */}
              {(!selectedEvidence.sealed_at || selectedEvidence.status !== 'SEALED') && (
                <button
                  type="button"
                  className="secondary-cta"
                  onClick={async () => {
                    try {
                      setIsSealing(true);
                      await sealEvidenceById(selectedEvidence.id);
                    } catch (err) {
                      setActionError(err instanceof Error ? err.message : 'Sealing failed');
                    } finally {
                      setIsSealing(false);
                    }
                  }}
                  disabled={isDownloading || isSealing}
                >
                  {isSealing ? 'Sealing…' : 'Seal evidence'}
                </button>
              )}
            </div>
          </div>

          <div className="detail-grid">
            <div className="preview-card">
              <EvidencePreview evidence={selectedEvidence} apiBase={API_BASE} />
            </div>

            <div className="facts-card">
              <div className="facts-header">
                <strong>{selectedEvidence.status === 'SEALED' || selectedEvidence.status === 'VERIFIED' ? 'Verified' : selectedEvidence.status === 'INTEGRITY FAILURE' ? 'Integrity failure' : 'Pending verification'}</strong>
                <span className={`status-badge ${selectedEvidence.status === 'SEALED' || selectedEvidence.status === 'VERIFIED' ? 'verified' : selectedEvidence.status === 'INTEGRITY FAILURE' ? 'failed' : 'pending'}`}>
                  {selectedEvidence.status === 'SEALED' || selectedEvidence.status === 'VERIFIED' ? 'VERIFIED' : selectedEvidence.status === 'INTEGRITY FAILURE' ? 'FAILURE' : 'PENDING'}
                </span>
              </div>

              <div className="facts-list">
                <div><label>Evidence name</label><span>{selectedEvidence.evidence_name || selectedEvidence.original_filename}</span></div>
                <div><label>Original filename</label><span>{selectedEvidence.original_filename}</span></div>
                <div><label>Case</label><span>{cases.find((item) => item.id === selectedEvidence.case_id)?.name ?? `Case ${selectedEvidence.case_id}`}</span></div>
                <div><label>Type</label><span>{selectedEvidence.evidence_type}</span></div>
                <div><label>Size</label><span>{selectedEvidence.file_size ? `${selectedEvidence.file_size} bytes` : 'Unknown'}</span></div>
                <div><label>SHA-256</label><span>{selectedEvidence.sha256 ?? 'Not sealed yet'}</span></div>
                <div><label>Manifest</label><span>{selectedEvidence.manifest_sha256 ?? 'Not yet created'}</span></div>
                <div><label>Sealed</label><span>{selectedEvidence.sealed_at ? new Date(selectedEvidence.sealed_at).toLocaleString() : 'Not sealed'}</span></div>
              </div>
            </div>
          </div>

          {verification && (
            <div className="detail-section">
              <VerificationResult
                state={verification.match ? 'verified' : 'failed'}
                title={verification.status}
                message={verification.match ? 'This evidence matches the recorded fingerprint.' : 'The stored evidence differs from the registered fingerprint.'}
                timestamp={verification.verified_at}
                details={[
                  { label: 'Recorded SHA-256', value: verification.recorded_sha256 },
                  { label: 'Current SHA-256', value: verification.current_sha256 },
                ]}
              />
            </div>
          )}

          <div className="detail-section">
            <h3>Chain of custody</h3>
            <div className="timeline">
              {(custodyEvents.length > 0 ? custodyEvents : [{ event_type: 'COLLECTED', created_at: selectedEvidence.sealed_at ?? new Date().toISOString() }]).map((event, index) => (
                <div key={`${event.event_type}-${index}`} className="timeline-item">
                  <span className="timeline-dot" />
                  <div>
                    <strong>{event.event_type || 'COLLECTED'}</strong>
                    <small>{event.created_at ? new Date(event.created_at).toLocaleString() : 'Recorded'}</small>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="detail-section share-panel">
            <h3>Sharing</h3>
            <div className="share-form-row">
              <input type="email" value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)} placeholder="Recipient email" />
              <button type="button" className="secondary-cta" onClick={handleLookupByEmail}>Check account</button>
              {foundRecipient && <div className="found-recipient"><strong>{foundRecipient.name}</strong><small>{foundRecipient.email}</small></div>}
              <div className="permission-toggle-row">
                {['VIEW', 'DOWNLOAD'].map((permission) => (
                  <label key={permission}>
                    <input type="checkbox" checked={sharePermissions.includes(permission)} onChange={() => setSharePermissions((current) => current.includes(permission) ? current.filter((item) => item !== permission) : [...current, permission])} />
                    {permission}
                  </label>
                ))}
              </div>
              <input type="datetime-local" value={shareExpiresAt} onChange={(event) => setShareExpiresAt(event.target.value)} />
              <button type="button" className="primary-cta" onClick={handleCreateShare} disabled={isSharing || !foundRecipient}>{isSharing ? 'Sending email…' : 'Share evidence and send email'}</button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
