import React, { useEffect, useMemo, useState } from 'react';
import { apiRequest } from './lib/api';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import AuthPage from './features/auth/AuthPage';
import CasePage from './features/cases/CasePage';
import DashboardPage from './features/dashboard/DashboardPage';
import EvidencePage from './features/evidence/EvidencePage';
import ReportsPage from './features/reports/ReportsPage';
import SettingsPage from './features/settings/SettingsPage';
import SharePage from './features/share/SharePage';
import VerificationPage from './features/verification/VerificationPage';
import { SearchContext, useSearch } from './lib/search';
import './styles.css';

const navItems = [
  { to: '/dashboard', label: 'Overview' },
  { to: '/cases', label: 'Cases' },
  { to: '/evidence', label: 'Evidence' },
  { to: '/verify', label: 'Verification' },
  { to: '/share', label: 'Sharing' },
  { to: '/reports', label: 'Reports' },
  { to: '/settings', label: 'Settings' },
];

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { query, setQuery } = useSearch();
  const [isReady, setIsReady] = useState(false);
  const [userEmail, setUserEmail] = useState('Investigator');

  useEffect(() => {
    const token = localStorage.getItem('verichain_token');
    if (!token) {
      navigate('/login');
      return;
    }
    // fetch current user profile for display (handle + investigator id)
    (async () => {
      try {
        const profile = await apiRequest<any>('/users/me');
        const displayName = (profile.handle && profile.handle.length > 0) ? profile.handle : (profile.name || profile.email || 'Investigator');
        setUserEmail(displayName);
        if (profile.email) localStorage.setItem('verichain_user_email', profile.email);
        if (profile.handle) localStorage.setItem('verichain_user_handle', profile.handle);
        if (profile.investigator_id) localStorage.setItem('verichain_investigator_id', profile.investigator_id);
      } catch (err) {
        setUserEmail(localStorage.getItem('verichain_user_email') ?? 'Investigator');
      } finally {
        setIsReady(true);
      }
    })();
  }, [navigate]);

  const activeUser = useMemo(() => {
    const value = userEmail.trim();
    if (!value) return 'V';
    return value.charAt(0).toUpperCase();
  }, [userEmail]);

  const routeLabel = useMemo(() => {
    const path = location.pathname;
    if (path.startsWith('/cases')) return 'Cases';
    if (path.startsWith('/evidence')) return 'Evidence';
    if (path.startsWith('/verify')) return 'Verification';
    if (path.startsWith('/share')) return 'Sharing';
    if (path.startsWith('/reports')) return 'Reports';
    if (path.startsWith('/settings')) return 'Settings';
    return 'Overview';
  }, [location.pathname]);

  if (!isReady) return <div className="auth-splash">Checking session…</div>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-wrap" aria-label="VeriChain home">
          <img src="/logos/icon-logo.png" alt="VeriChain" style={{height:48}} />
          <div>
            <span className="brand-name">VeriChain</span>
            <small className="brand-subtitle">Evidence integrity</small>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              {item.label}
            </NavLink>
          ))}

          <button
            className="logout-button"
            onClick={() => {
              localStorage.removeItem('verichain_token');
              localStorage.removeItem('verichain_user_email');
              window.location.href = '/login';
            }}
          >
            Logout
          </button>
        </nav>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="page-context">
            <span className="crumb-label">Investigation workspace</span>
            <div className="crumb-row">
              <span>VeriChain</span>
              <span className="crumb-separator">/</span>
              <strong>{routeLabel}</strong>
            </div>
          </div>

          <div className="topbar-actions" role="navigation" aria-label="Topbar actions">
            <div className="search-box" aria-label="Search">
              <span className="search-icon">⌕</span>
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search cases, evidence, reports…"
                aria-label="Search the application"
              />
            </div>
            <button type="button" className="toolbar-button">Alerts</button>
            <div className="user-pill" aria-label="Current user">
              <div className="user-avatar">{activeUser}</div>
              <div className="user-meta">
                <strong>{userEmail}</strong>
                <small>Investigator</small>
              </div>
            </div>
          </div>
        </header>

        <main className="content-shell">{children}</main>
      </div>
    </div>
  );
}

function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [query, setQuery] = useState('');

  useEffect(() => {
    setIsAuthenticated(Boolean(localStorage.getItem('verichain_token')));
    setAuthChecked(true);
  }, []);

  if (!authChecked) return <div className="auth-splash">Loading VeriChain…</div>;

  return (
    <SearchContext.Provider value={{ query, setQuery }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <AuthPage mode="login" />} />
          <Route path="/register" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <AuthPage mode="register" />} />
          <Route path="/dashboard" element={<ProtectedLayout><DashboardPage /></ProtectedLayout>} />
          <Route path="/cases" element={<ProtectedLayout><CasePage /></ProtectedLayout>} />
          <Route path="/evidence" element={<ProtectedLayout><EvidencePage /></ProtectedLayout>} />
          <Route path="/evidence/register" element={<ProtectedLayout><EvidencePage /></ProtectedLayout>} />
          <Route path="/verify" element={<ProtectedLayout><VerificationPage /></ProtectedLayout>} />
          <Route path="/verify/presented" element={<ProtectedLayout><VerificationPage /></ProtectedLayout>} />
          <Route path="/share" element={<ProtectedLayout><SharePage /></ProtectedLayout>} />
          <Route path="/reports" element={<ProtectedLayout><ReportsPage /></ProtectedLayout>} />
          <Route path="/settings" element={<ProtectedLayout><SettingsPage /></ProtectedLayout>} />
          <Route path="/" element={<Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />} />
          <Route path="*" element={<Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />} />
        </Routes>
      </BrowserRouter>
    </SearchContext.Provider>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
