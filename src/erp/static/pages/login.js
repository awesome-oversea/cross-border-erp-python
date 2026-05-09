import api from '../js/api.js';

export function render() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="login-wrapper">
      <div class="login-card">
        <div style="margin-bottom:8px">
          <span style="display:inline-block;padding:5px 10px;border-radius:999px;border:1px solid rgba(245,156,87,0.28);background:rgba(245,156,87,0.08);color:var(--accent);font:700 11px var(--mono);letter-spacing:0.12em;text-transform:uppercase">Cross-Border ERP</span>
        </div>
        <h1>登录系统</h1>
        <p class="login-sub">跨境电商 ERP 管理平台 · 请输入您的账号信息</p>
        <form id="loginForm">
          <div class="form-group">
            <label>租户 ID</label>
            <input type="text" id="loginTenant" class="form-input" placeholder="请输入租户标识" value="default" required>
          </div>
          <div class="form-group">
            <label>用户名</label>
            <input type="text" id="loginUser" class="form-input" placeholder="请输入用户名" required autocomplete="username">
          </div>
          <div class="form-group">
            <label>密码</label>
            <input type="password" id="loginPass" class="form-input" placeholder="请输入密码" required autocomplete="current-password">
          </div>
          <div id="loginError" style="display:none;color:var(--danger);font-size:13px;margin-bottom:16px;padding:10px;border-radius:8px;background:rgba(255,118,118,0.08);border:1px solid rgba(255,118,118,0.2)"></div>
          <button type="submit" class="btn btn-primary btn-block" id="loginBtn" style="padding:14px;font-size:15px">登 录</button>
        </form>
        <div style="margin-top:24px;text-align:center;color:var(--dim);font-size:12px">
          跨境电商 ERP v0.1.0 · Powered by FastAPI + DDD
        </div>
      </div>
    </div>
  `;

  document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errEl = document.getElementById('loginError');
    const btn = document.getElementById('loginBtn');
    errEl.style.display = 'none';

    const username = document.getElementById('loginUser').value.trim();
    const password = document.getElementById('loginPass').value;
    const tenantId = document.getElementById('loginTenant').value.trim();

    if (!username || !password || !tenantId) {
      errEl.textContent = '请填写所有字段';
      errEl.style.display = 'block';
      return;
    }

    btn.disabled = true;
    btn.textContent = '登录中...';

    try {
      await api.login(username, password, tenantId);
      window.location.hash = '#/dashboard';
    } catch (err) {
      errEl.textContent = err.message || '登录失败，请检查账号密码';
      errEl.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = '登 录';
    }
  });
}
