import api from '../js/api.js';
import { formatNumber, formatCurrency, loadingSpinner } from '../js/utils.js';

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>商业智能</h2><p>指标看板、数据报表、预警分析</p></div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div><h3>核心指标</h3><p>经营关键指标概览</p></div>
        <span style="padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700;color:var(--mint);background:rgba(123,210,176,0.1);border:1px solid rgba(123,210,176,0.25)">LIVE</span>
      </div>
      <div class="metric-grid" id="biMetrics">${loadingSpinner()}</div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <div class="panel-header"><div><h3>指标趋势</h3><p>近 7 日经营指标变化</p></div></div>
        <div id="biMetricTrends">${loadingSpinner()}</div>
      </div>
      <div class="panel">
        <div class="panel-header"><div><h3>预警事件</h3><p>需要关注的异常指标</p></div></div>
        <div id="biAlerts">${loadingSpinner()}</div>
      </div>
    </div>
  `;

  loadMetrics();
  loadMetricTrends();
  loadAlerts();
}

async function loadMetrics() {
  const el = document.getElementById('biMetrics');
  try {
    const res = await api.get('/api/bi/v1/metrics', { category: 'core' });
    const metrics = res.data?.items || res.data || [];
    if (!metrics.length) {
      el.innerHTML = `
        <div class="metric-tile"><strong style="color:var(--sky)">-</strong><span>GMV</span><small>近 7 日</small></div>
        <div class="metric-tile"><strong style="color:var(--mint)">-</strong><span>订单量</span><small>近 7 日</small></div>
        <div class="metric-tile"><strong style="color:var(--accent)">-</strong><span>毛利率</span><small>近 7 日</small></div>
        <div class="metric-tile"><strong style="color:var(--amber)">-</strong><span>退款率</span><small>近 7 日</small></div>
      `;
      return;
    }
    el.innerHTML = metrics.slice(0, 4).map(m => `
      <div class="metric-tile">
        <strong style="color:var(--sky)">${m.value ?? '-'}</strong>
        <span>${m.name || m.metric_key}</span>
        <small>${m.period || ''}</small>
      </div>
    `).join('');
  } catch {
    el.innerHTML = `
      <div class="metric-tile"><strong style="color:var(--sky)">-</strong><span>GMV</span></div>
      <div class="metric-tile"><strong style="color:var(--mint)">-</strong><span>订单量</span></div>
      <div class="metric-tile"><strong style="color:var(--accent)">-</strong><span>毛利率</span></div>
      <div class="metric-tile"><strong style="color:var(--amber)">-</strong><span>退款率</span></div>
    `;
  }
}

async function loadMetricTrends() {
  const el = document.getElementById('biMetricTrends');
  try {
    const res = await api.get('/api/bi/v1/metrics/trends', { days: 7 });
    const trends = res.data || [];
    if (!trends.length) {
      el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">暂无趋势数据</div>';
      return;
    }
    el.innerHTML = trends.map(t => `
      <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)">
        <span style="font-weight:600;font-size:13px;min-width:80px">${t.metric_name || t.metric_key}</span>
        <span style="color:var(--accent);font-family:var(--mono)">${t.value ?? '-'}</span>
        <span style="color:var(--dim);font-size:11px">${t.date || ''}</span>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">趋势数据加载失败</div>';
  }
}

async function loadAlerts() {
  const el = document.getElementById('biAlerts');
  try {
    const res = await api.get('/api/bi/v1/alerts', { page: 1, page_size: 5 });
    const alerts = res.data?.items || res.data || [];
    if (!alerts.length) {
      el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--mint)">✓ 暂无预警事件</div>';
      return;
    }
    el.innerHTML = alerts.map(a => `
      <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)">
        <span style="color:var(--amber);font-size:16px">⚠</span>
        <span style="flex:1;font-size:13px">${a.message || a.alert_name || '预警'}</span>
        <span style="font-size:11px;color:var(--dim)">${a.severity || ''}</span>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">预警数据加载失败</div>';
  }
}
