import api from '../js/api.js';
import { formatNumber, formatCurrency, statusBadge, buildTable, loadingSpinner } from '../js/utils.js';

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div>
        <h2>管理驾驶舱</h2>
        <p>经营总览、核心链路和关键执行面</p>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost btn-sm" onclick="location.reload()">刷新数据</button>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div><h3>经营脉搏</h3><p>今日关键经营指标</p></div>
        <span style="padding:4px 10px;border-radius:999px;font-size:11px;font-weight:700;color:var(--mint);background:rgba(123,210,176,0.1);border:1px solid rgba(123,210,176,0.25)">LIVE</span>
      </div>
      <div class="metric-grid" id="dashMetrics">
        ${loadingSpinner()}
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <div class="panel-header">
          <div><h3>经营主链路</h3><p>商品 → Listing → 订单 → 库存 → 履约 → 售后 → 结算</p></div>
        </div>
        <div id="dashPipeline" style="display:flex;flex-direction:column;gap:12px"></div>
      </div>

      <div class="panel">
        <div class="panel-header">
          <div><h3>异常告警</h3><p>需要干预的关键异常</p></div>
        </div>
        <div id="dashAlerts">${loadingSpinner()}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div><h3>最近订单</h3><p>最新 10 条订单动态</p></div>
        <button class="btn btn-ghost btn-sm" onclick="erpNav('/oms')">查看全部 →</button>
      </div>
      <div id="dashOrders">${loadingSpinner()}</div>
    </div>
  `;

  loadDashboard();
}

async function loadDashboard() {
  await Promise.all([
    loadMetrics(),
    loadPipeline(),
    loadAlerts(),
    loadRecentOrders(),
  ]);
}

async function loadMetrics() {
  const el = document.getElementById('dashMetrics');
  try {
    const [ordersRes, inventoryRes, settlementRes] = await Promise.allSettled([
      api.get('/api/oms/v1/orders', { page: 1, page_size: 1 }),
      api.get('/api/wms/v1/inventory/summary'),
      api.get('/api/fms/v1/settlements', { page: 1, page_size: 1 }),
    ]);

    const orderTotal = ordersRes.status === 'fulfilled' ? (ordersRes.value.data?.total || 0) : '-';
    const invData = inventoryRes.status === 'fulfilled' ? inventoryRes.value.data : null;
    const settleTotal = settlementRes.status === 'fulfilled' ? (settlementRes.value.data?.total || 0) : '-';

    el.innerHTML = `
      <div class="metric-tile">
        <strong style="color:var(--sky)">${formatNumber(orderTotal)}</strong>
        <span>订单总数</span>
        <small>全部渠道订单</small>
      </div>
      <div class="metric-tile">
        <strong style="color:var(--mint)">${invData ? formatNumber(invData.total_quantity || 0) : '-'}</strong>
        <span>库存总量</span>
        <small>可用库存 SKU</small>
      </div>
      <div class="metric-tile">
        <strong style="color:var(--amber)">${invData ? formatNumber(invData.low_stock_count || 0) : '-'}</strong>
        <span>低库存 SKU</span>
        <small>低于安全阈值</small>
      </div>
      <div class="metric-tile">
        <strong style="color:var(--accent)">${formatNumber(settleTotal)}</strong>
        <span>结算单数</span>
        <small>待处理结算</small>
      </div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim);padding:24px;text-align:center">指标数据加载失败</div>';
  }
}

async function loadPipeline() {
  const el = document.getElementById('dashPipeline');
  const steps = [
    { label: '商品主数据', path: '/pdm', count: '-', icon: '📦' },
    { label: '渠道与 Listing', path: '/som', count: '-', icon: '🏪' },
    { label: '订单中心', path: '/oms', count: '-', icon: '📋' },
    { label: '库存控制', path: '/wms', count: '-', icon: '📊' },
    { label: '履约物流', path: '/tms', count: '-', icon: '🚚' },
    { label: '售后中心', path: '/crm', count: '-', icon: '🔄' },
    { label: '结算利润', path: '/fms', count: '-', icon: '💰' },
  ];

  el.innerHTML = steps.map(s => `
    <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:10px;border:1px solid var(--line);background:rgba(255,255,255,0.02);cursor:pointer" onclick="erpNav('${s.path}')">
      <span style="font-size:20px">${s.icon}</span>
      <span style="flex:1;font-weight:600;font-size:13px">${s.label}</span>
      <span style="color:var(--dim);font-size:12px">→</span>
    </div>
  `).join('');
}

async function loadAlerts() {
  const el = document.getElementById('dashAlerts');
  try {
    const res = await api.get('/api/wms/v1/inventory/alerts', { page: 1, page_size: 5 });
    const alerts = res.data?.items || res.data || [];
    if (!alerts.length) {
      el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--mint)">✓ 暂无异常告警</div>';
      return;
    }
    el.innerHTML = alerts.map(a => `
      <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)">
        <span style="color:var(--amber);font-size:16px">⚠</span>
        <span style="flex:1;font-size:13px">${a.sku_code || a.message || '库存预警'}</span>
        <span style="font-size:11px;color:var(--dim)">${a.warehouse_name || ''}</span>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">告警数据暂不可用</div>';
  }
}

async function loadRecentOrders() {
  const el = document.getElementById('dashOrders');
  try {
    const res = await api.get('/api/oms/v1/orders', { page: 1, page_size: 10 });
    const orders = res.data?.items || res.data || [];
    if (!orders.length) {
      el.innerHTML = '<div class="empty-state"><div class="empty-icon">📋</div><h3>暂无订单</h3></div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '订单号', key: 'order_no' },
      { label: '渠道', key: 'platform', render: r => r.platform || '-' },
      { label: '金额', key: 'total_amount', render: r => formatCurrency(r.total_amount, r.currency || 'CNY') },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '下单时间', key: 'order_date', render: r => r.order_date ? new Date(r.order_date).toLocaleString('zh-CN') : '-' },
    ], orders);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">订单数据加载失败</div>';
  }
}
