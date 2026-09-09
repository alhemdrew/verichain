import { useEffect, useState } from 'react';
import { apiRequest } from '../../lib/api';

type CaseItem = {
  id: number;
  name: string;
  description?: string | null;
  status: string;
};

export default function CasePage() {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('OPEN');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function loadCases() {
    try {
      const data = await apiRequest<CaseItem[]>('/cases');
      setCases(data);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to load cases');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCases();
  }, []);

  async function createCase() {
    if (!name.trim()) {
      setError('Case name is required');
      return;
    }
    try {
      setError('');
      await apiRequest('/cases', {
        method: 'POST',
        body: JSON.stringify({ name, description, status }),
      });
      setName('');
      setDescription('');
      setStatus('OPEN');
      await loadCases();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to create case');
    }
  }

  return (
    <div className="page-shell">
      <div className="page-header-row">
        <div>
          <p className="eyebrow">Case workspace</p>
          <h2>Investigation cases</h2>
        </div>
      </div>

      <div className="case-create-grid">
        <div className="mini-panel">
          <div className="section-header-row">
            <h3>Create case</h3>
            <span className="section-tag">New</span>
          </div>
          <div className="stacked-form">
            <label>
              <span>Case name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label>
              <span>Status</span>
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="OPEN">Open</option>
                <option value="ACTIVE">Active</option>
                <option value="CLOSED">Closed</option>
              </select>
            </label>
            <label>
              <span>Description</span>
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
            </label>
            <button type="button" onClick={createCase}>Create case</button>
          </div>
          {error && <div className="auth-error" style={{ marginTop: '12px' }}>{error}</div>}
        </div>

        <div className="mini-panel">
          <div className="section-header-row">
            <h3>Case inventory</h3>
            <span className="section-tag subtle">{cases.length} total</span>
          </div>
          {loading ? <p className="muted-text">Loading cases…</p> : cases.length === 0 ? <p className="muted-text">No cases available.</p> : (
            <ul className="case-list">
              {cases.map((caseItem) => (
                <li key={caseItem.id} className="case-card">
                  <div className="case-card-top">
                    <div>
                      <strong>{caseItem.name}</strong>
                      <small>Case #{caseItem.id}</small>
                    </div>
                    <span className={`status-badge ${caseItem.status === 'OPEN' ? 'warning' : caseItem.status === 'CLOSED' ? 'muted' : 'success'}`}>
                      {caseItem.status}
                    </span>
                  </div>
                  <p>{caseItem.description ?? 'No description provided.'}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
