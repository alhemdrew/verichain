const DEFAULT_API_BASE = 'http://localhost:8000';

export function getApiBase() {
  return import.meta.env.VITE_API_BASE ?? DEFAULT_API_BASE;
}

export function getAuthHeaders() {
  const token = localStorage.getItem('verichain_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  // centralize fetch with auth + 401 handling
  const base = getApiBase();
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string> ?? {}) };
  // allow callers to send FormData (multipart) by skipping content-type override
  if (!(init && init.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';
  }
  Object.assign(headers, getAuthHeaders());

  const opts: RequestInit = {
    ...init,
    headers,
  };

  // if body is a plain object and not FormData, stringify it
  if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
    opts.body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${base}${path}`, opts);
  // handle 401 centrally: clear token and redirect to login
  if (res.status === 401) {
    localStorage.removeItem('verichain_token');
    window.location.assign('/login');
    throw new Error('Unauthorized');
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? 'Request failed');
  return data as T;
}
