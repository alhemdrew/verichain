import { useEffect, useMemo, useState } from 'react';
import { apiRequest } from '../../lib/api';

type CaseItem = {
  id: number;
  name: string;
  status: string;
  description?: string | null;
};

type EvidenceItem = {
  id: string;
  case_id: number;
  original_filename: string;
  status: string;
  sha256?: string | null;
  manifest_sha256?: string | null;
  signature?: string | null;
  sync_state?: string | null;
  not_synced?: boolean | null;
  organization_id: number;
  evidence_type?: string;
};

export default function DashboardPage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const caseData = await apiRequest<CaseItem[]>('/cases');
        setCases(caseData);

        const aggregated: EvidenceItem[] = [];
        for (const item of caseData) {
          const caseEvidence = await apiRequest<EvidenceItem[]>(`/cases/${item.id}/evidence`);
          aggregated.push(...caseEvidence);
        }
        setEvidence(aggregated);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const summary = useMemo(() => {
    const totalCases = cases.length;
    const totalEvidence = evidence.length;
    const verified = evidence.filter((item) => item.status === 'SEALED' || item.status === 'VERIFIED').length;
    const pendingSync = evidence.filter((item) => item.not_synced || item.sync_state === 'LOCAL_ONLY').length;
    const failed = evidence.filter((item) => item.status === 'INTEGRITY FAILURE').length;
    return { totalCases, totalEvidence, verified, pendingSync, failed };
  }, [cases, evidence]);

  if (loading) return <div className="placeholder-card"><h2>Dashboard</h2><p>Loading case and evidence overview…</p></div>;

  return (
    <div className="page-shell dashboard-shell">
      <div className="page-header-row">
        <div className="dashboard-hero-copy">
          <p className="eyebrow">Good morning, Investigator.</p>
          <h2>VeriChain — Digital Evidence Integrity</h2>
          <p className="muted-text">Protect what matters. Prove what happened.</p>
        </div>
        <div className="dashboard-actions">
          <button className="primary-cta" onClick={() => window.location.assign('/evidence/register')}>+ REGISTER EVIDENCE</button>
          <button className="secondary-cta" onClick={() => window.location.assign('/verify/presented')}>VERIFY A PRESENTED FILE</button>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <span>Active cases</span>
          <strong>{summary.totalCases}</strong>
        </div>
        <div className="stat-card">
          <span>Registered evidence</span>
          <strong>{summary.totalEvidence}</strong>
        </div>
        <div className="stat-card">
          <span>Integrity verified</span>
          <strong>{summary.verified}</strong>
        </div>
        <div className="stat-card">
          <span>Local-only</span>
          <strong>{summary.pendingSync}</strong>
        </div>
        <div className="stat-card warning">
          <span>Integrity issues</span>
          <strong>{summary.failed}</strong>
        </div>
      </div>

      <div className="dashboard-panels">
        <section className="mini-panel">
          <div className="section-header-row">
            <h3>Evidence Command Center</h3>
            <span className="section-tag">Primary</span>
          </div>
          <p className="muted-text">Start here to register evidence, preserve originals, and verify integrity.</p>
          <div style={{marginTop:12}}>
            <button className="primary-cta" onClick={() => window.location.assign('/evidence/register')}>+ REGISTER EVIDENCE</button>
            <button style={{marginLeft:8}} className="secondary-cta" onClick={() => window.location.assign('/verify/presented')}>VERIFY PRESENTED FILE</button>
          </div>
        </section>

        <section className="mini-panel">
          <div className="section-header-row">
            <h3>Recent evidence</h3>
            <span className="section-tag subtle">Security</span>
          </div>
          {evidence.length === 0 ? <p className="muted-text">No evidence has been captured yet.</p> : (
            <ul className="list-stack">
              {evidence.slice(0, 6).map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.original_filename}</strong>
                    <small>{item.status}</small>
                  </div>
                  <span>{item.sync_state ?? 'LOCAL'} • {item.manifest_sha256 ? 'sealed' : 'not sealed'}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
