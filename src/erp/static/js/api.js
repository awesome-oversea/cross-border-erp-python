const API_BASE = window.__ERP_API_BASE__ || '';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('erp_access_token') || '';
    this.tenantId = localStorage.getItem('erp_tenant_id') || '';
    this.refreshToken = localStorage.getItem('erp_refresh_token') || '';
  }

  setAuth(data) {
    this.token = data.access_token;
    this.refreshToken = data.refresh_token;
    this.tenantId = data.tenant_id;
    localStorage.setItem('erp_access_token', data.access_token);
    localStorage.setItem('erp_refresh_token', data.refresh_token);
    localStorage.setItem('erp_tenant_id', data.tenant_id);
    localStorage.setItem('erp_user_id', data.user_id);
    localStorage.setItem('erp_display_name', data.display_name);
  }

  clearAuth() {
    this.token = '';
    this.refreshToken = '';
    this.tenantId = '';
    localStorage.removeItem('erp_access_token');
    localStorage.removeItem('erp_refresh_token');
    localStorage.removeItem('erp_tenant_id');
    localStorage.removeItem('erp_user_id');
    localStorage.removeItem('erp_display_name');
  }

  get isAuthenticated() {
    return !!this.token;
  }

  get displayName() {
    return localStorage.getItem('erp_display_name') || '';
  }

  get userId() {
    return localStorage.getItem('erp_user_id') || '';
  }

  async request(method, path, body = null, opts = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'X-Tenant-ID': this.tenantId,
      'X-Actor-ID': this.userId,
      'X-Actor-Type': 'user',
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    const fetchOpts = { method, headers };
    if (body && method !== 'GET') {
      fetchOpts.body = JSON.stringify(body);
    }

    let url = `${API_BASE}${path}`;
    if (opts.params) {
      const sp = new URLSearchParams();
      for (const [k, v] of Object.entries(opts.params)) {
        if (v !== undefined && v !== null && v !== '') sp.set(k, v);
      }
      const qs = sp.toString();
      if (qs) url += `?${qs}`;
    }

    const res = await fetch(url, fetchOpts);
    if (res.status === 401 && !opts._noRetry) {
      const refreshed = await this._tryRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.token}`;
        const retry = await fetch(url, { method, headers, body: fetchOpts.body });
        return retry.json();
      }
      this.clearAuth();
      window.location.hash = '#/login';
      throw new Error('Session expired');
    }
    return res.json();
  }

  async _tryRefresh() {
    if (!this.refreshToken) return false;
    try {
      const res = await fetch(`${API_BASE}/api/iam/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });
      const data = await res.json();
      if (data.code === 0 && data.data) {
        this.setAuth(data.data);
        return true;
      }
    } catch {}
    return false;
  }

  async login(username, password, tenantId) {
    const res = await fetch(`${API_BASE}/api/iam/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, tenant_id: tenantId }),
    });
    const data = await res.json();
    if (data.code === 0 && data.data) {
      this.setAuth(data.data);
      return data.data;
    }
    throw new Error(data.message || 'Login failed');
  }

  async logout() {
    try {
      await this.request('POST', '/api/iam/v1/auth/logout', {
        refresh_token: this.refreshToken,
      });
    } catch {}
    this.clearAuth();
  }

  get(path, params) { return this.request('GET', path, null, { params }); }
  post(path, body) { return this.request('POST', path, body); }
  put(path, body) { return this.request('PUT', path, body); }
  delete(path) { return this.request('DELETE', path); }
}

const api = new ApiClient();
export default api;
