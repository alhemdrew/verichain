import { useEffect, useMemo, useState } from 'react';
import { apiRequest } from '../../lib/api';
import { useSearch } from '../../lib/search';

type EvidenceItem = {
  id: string;
  original_filename: string;
  status: string;
  case_id: number;
  sha256?: string | null;
  manifest_sha256?: string | null;
};

type ReportItem = {
  evidence_id: string;
  verification_status: string;
  sha256_status: string;
  manifest_status: string;
  signature_status: string;
  custody_status: string;
  generated_at: string;
};

export default function ReportsPage() {
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [report, setReport] = useState<ReportItem | null>(null);
  const [error, setError] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSealing, setIsSealing] = useState(false);
  const [isSigning, setIsSigning] = useState(false);
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
        setError(err instanceof Error ? err.message : 'Unable to load reports');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  useEffect(() => {
    if (!selectedEvidenceId) return;
    apiRequest<ReportItem>(`/evidence/${selectedEvidenceId}/report`)
      .then((data) => setReport(data))
      .catch(() => setReport(null));
  }, [selectedEvidenceId]);

  const selectedEvidence = evidence.find((item) => item.id === selectedEvidenceId) ?? null;

  async function handleDownloadPdf(mode: 'summary' | 'detailed' = 'summary') {
    if (!selectedEvidenceId) return;

    try {
      const token = localStorage.getItem('verichain_token');
      const base = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';
      const urlFetch = `${base}/evidence/${selectedEvidenceId}/report.pdf?mode=${mode}&_ts=${Date.now()}`;
      const res = await fetch(urlFetch, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) {
        throw new Error('Report PDF is unavailable for the selected evidence');
      }
      const disposition = res.headers.get('Content-Disposition') || '';
      let filename = `verichain-report-${mode}.pdf`;
      const match = /filename=\"(?<name>[^\"]+)\"/.exec(disposition);
      if (match && match.groups && match.groups.name) filename = match.groups.name;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 15000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to download the report PDF');
    }
  }

  async function handleSeal() {
    if (!selectedEvidenceId) return;
    setError('');
    setIsSealing(true);
    try {
      await apiRequest(`/evidence/${selectedEvidenceId}/seal`, { method: 'POST' });
      // refresh evidence list and report
      const caseData = await apiRequest<{ id: number }[]>('/cases');
      const allEvidence: EvidenceItem[] = [];
      for (const item of caseData) {
        const caseEvidence = await apiRequest<EvidenceItem[]>(`/cases/${item.id}/evidence`);
        allEvidence.push(...caseEvidence);
      }
      setEvidence(allEvidence);
      const updated = await apiRequest<ReportItem>(`/evidence/${selectedEvidenceId}/report`);
      setReport(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sealing failed');
    } finally {
      setIsSealing(false);
    }
  }

  async function handleSign() {
    if (!selectedEvidenceId) return;
    setError('');
    setIsSigning(true);
    try {
      await apiRequest(`/evidence/${selectedEvidenceId}/sign`, { method: 'POST' });
      const updated = await apiRequest<ReportItem>(`/evidence/${selectedEvidenceId}/report`);
      setReport(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signing failed');
    } finally {
      setIsSigning(false);
    }
  }

  if (loading) return <div className="placeholder-card"><h2>Reports</h2><p>Loading integrity data…</p></div>;

  return (
    <div className="placeholder-card" style={{ maxWidth: '1100px' }}>
      <div className="page-header-row">
        <div>
          <p className="eyebrow">Integrity report</p>
          <h2>Evidence verification reports</h2>
        </div>
      </div>

      {error && <div className="auth-error">{error}</div>}

      <div className="evidence-layout">
        <div className="evidence-list">
          {filteredEvidence.length === 0 ? (
            <p className="muted-text">{normalizedQuery ? 'No evidence matches the current search.' : 'No evidence yet to report on.'}</p>
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
                  <p className="eyebrow">Current record</p>
                  <h3>{selectedEvidence.original_filename}</h3>
                </div>
              </div>

              <div className="info-grid">
                <div><label>SHA-256</label><span>{selectedEvidence.sha256 ?? 'Not sealed'}</span></div>
                <div><label>Manifest</label><span>{selectedEvidence.manifest_sha256 ?? 'Not available'}</span></div>
                <div><label>Status</label><span>{selectedEvidence.status}</span></div>
              </div>

              {report ? (
                <div className="verification-panel verified">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    <h4 style={{ margin: 0 }}>Report summary</h4>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <button type="button" className="secondary-cta" onClick={() => handleDownloadPdf('summary')} disabled={isSealing || isSigning}>Download summary</button>
                        <button type="button" className="secondary-cta" onClick={() => handleDownloadPdf('detailed')} disabled={isSealing || isSigning}>Download detailed</button>
                        {/* Show Seal/Sign when appropriate */}
                        <button type="button" className="secondary-cta" onClick={handleSeal} disabled={isSealing || isSigning}>{isSealing ? 'Sealing…' : 'Seal evidence'}</button>
                        <button type="button" className="secondary-cta" onClick={handleSign} disabled={isSealing || isSigning}>{isSigning ? 'Signing…' : 'Sign evidence'}</button>
                      </div>
                  </div>
                  <p>Verification status: {report.verification_status}</p>
                  <p>SHA-256 status: {report.sha256_status}</p>
                  <p>Manifest status: {report.manifest_status}</p>
                  <p>Signature status: {report.signature_status}</p>
                  <p>Custody status: {report.custody_status}</p>
                  <p>Generated at: {report.generated_at}</p>
                </div>
              ) : (
                <p className="muted-text">No integrity report available yet.</p>
              )}
            </>
          ) : (
            <p className="muted-text">Choose evidence to view its integrity report.</p>
          )}
        </div>
      </div>
    </div>
  );
}
