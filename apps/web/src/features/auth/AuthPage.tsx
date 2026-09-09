import { FormEvent, useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organization, setOrganization] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('verichain_token');
    const storedEmail = localStorage.getItem('verichain_user_email');
    if (token && storedEmail) {
      navigate('/dashboard');
      return;
    }
    setSessionReady(true);
  }, [navigate]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    const payload = mode === 'register'
      ? { name, email, password, organization_name: organization }
      : { email, password };

    const endpoint = mode === 'register' ? `${API_BASE}/auth/register` : `${API_BASE}/auth/login`;

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item: { msg?: string; message?: string }) => item.msg ?? item.message ?? 'Validation error').join('; ')
          : typeof data.detail === 'string'
            ? data.detail
            : 'Authentication failed';
        throw new Error(detail || 'Authentication failed');
      }

      localStorage.setItem('verichain_token', data.access_token);
      localStorage.setItem('verichain_user_email', email);
      navigate('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!sessionReady) {
    return <div className="auth-splash">Loading…</div>;
  }

  return (
    <div className="auth-shell">
      <div className="auth-panel">
        <div className="brand-wrap auth-brand-wrap" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
          <img src="/logos/primary-horizontal-logo.png" alt="VeriChain" style={{ width: 220, maxWidth: '100%', height: 'auto', objectFit: 'contain' }} />
        </div>

        <div className="auth-intro">
          <h1>{mode === 'login' ? 'Secure access' : 'Create a secure workspace'}</h1>
          <p>{mode === 'login' ? 'Access case records, verify integrity, and manage evidence custody.' : 'Set up the investigation workspace for your evidence operations.'}</p>
        </div>

        <form onSubmit={submit} className="auth-form">

          {mode === 'register' && (
            <label>
              <span>Name</span>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
          )}

          <label>
            <span>Email</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>

          {mode === 'register' && (
            <label>
              <span>Organization</span>
              <input value={organization} onChange={(e) => setOrganization(e.target.value)} placeholder="Optional" />
            </label>
          )}

          <label>
            <span>Password</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Please wait…' : mode === 'login' ? 'Login' : 'Create account'}
          </button>

          <div className="auth-switch">
            {mode === 'login' ? (
              <Link to="/register">Need an account? Register</Link>
            ) : (
              <Link to="/login">Already have an account? Login</Link>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}

export default AuthPage;
