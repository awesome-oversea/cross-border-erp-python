import api from '../js/api.js';
import { formatCurrency, formatDateTime, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>履约与物流</h2><p>发货管理、物流追踪、运费对比</p></div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <div class="panel-header"><div><h3>发货管理</h3><p>待发货与已发货订单</p></div></div>
        <div id="tmsShipments">${loadingSpinner()}</div>
      </div>
      <div class="panel">
        <div class="panel-header"><div><h3>运费估算</h3><p>物流渠道运费对比</p></div></div>
        <div style="padding:16px 0">
          <div class="form-group"><label>目的国</label><input id="tmsDestCountry" class="form-input" placeholder="如 US, UK, DE" value="US"></div>
          <div class="form-group"><label>重量(kg)</label><input id="tmsWeight" class="form-input" type="number" step="0.01" value="0.5"></div>
          <button class="btn btn-primary btn-sm" onclick="erpEstimateShipping()">估算运费</button>
          <div id="tmsRateResult" style="margin-top:16px"></div>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header"><div><h3>物流追踪</h3><p>包裹实时追踪</p></div></div>
      <div class="filter-bar">
        <input id="tmsTrackingNo" class="form-input" placeholder="输入追踪号" style="min-width:200px">
        <button class="btn btn-ghost btn-sm" onclick="erpQueryTracking()">查询</button>
      </div>
      <div id="tmsTrackingResult"></div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadShipments(); };
  loadShipments();
}

async function loadShipments() {
  const el = document.getElementById('tmsShipments');
  try {
    const res = await api.get('/api/tms/v1/shipments', { page: currentPage, page_size: PAGE_SIZE });
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    if (!items.length) {
      el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">暂无发货记录</div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '发货单号', key: 'shipment_no' },
      { label: '承运商', key: 'carrier', render: r => r.carrier || '-' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '追踪号', key: 'tracking_no', render: r => r.tracking_no || '-' },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">数据加载失败</div>';
  }
}

window.erpEstimateShipping = async function() {
  const el = document.getElementById('tmsRateResult');
  const dest = document.getElementById('tmsDestCountry').value;
  const weight = parseFloat(document.getElementById('tmsWeight').value) || 0;
  if (!dest) { el.innerHTML = '<div style="color:var(--danger)">请输入目的国</div>'; return; }
  el.innerHTML = loadingSpinner();
  try {
    const res = await api.post('/api/tms/v1/shipping/estimate', {
      origin_country: 'CN',
      destination_country: dest,
      weight,
      package: { length: 30, width: 20, height: 10 },
    });
    const methods = res.data?.methods || res.data || [];
    if (!methods.length) {
      el.innerHTML = '<div style="color:var(--dim)">未找到可用渠道</div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '渠道', key: 'method_name', render: r => r.method_name || r.name || '-' },
      { label: '承运商', key: 'carrier', render: r => r.carrier || '-' },
      { label: '运费', key: 'total_cost', render: r => formatCurrency(r.total_cost || r.cost) },
      { label: '时效(天)', key: 'estimated_days', render: r => r.estimated_days || '-' },
    ], methods);
  } catch {
    el.innerHTML = '<div style="color:var(--dim)">运费估算失败</div>';
  }
};

window.erpQueryTracking = async function() {
  const el = document.getElementById('tmsTrackingResult');
  const trackingNo = document.getElementById('tmsTrackingNo').value.trim();
  if (!trackingNo) { el.innerHTML = '<div style="color:var(--danger)">请输入追踪号</div>'; return; }
  el.innerHTML = loadingSpinner();
  try {
    const res = await api.get(`/api/tms/v1/tracking/${trackingNo}`);
    const data = res.data || {};
    el.innerHTML = `
      <div style="padding:16px;border-radius:12px;border:1px solid var(--line);background:rgba(255,255,255,0.02)">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div><label style="color:var(--dim);font-size:12px">追踪号</label><div style="font-family:var(--mono)">${data.tracking_no || trackingNo}</div></div>
          <div><label style="color:var(--dim);font-size:12px">状态</label><div>${statusBadge(data.status || 'unknown')}</div></div>
          <div><label style="color:var(--dim);font-size:12px">承运商</label><div>${data.carrier || '-'}</div></div>
          <div><label style="color:var(--dim);font-size:12px">预计到达</label><div>${data.estimated_delivery ? formatDateTime(data.estimated_delivery) : '-'}</div></div>
        </div>
        ${data.events ? `<div style="margin-top:16px"><label style="color:var(--dim);font-size:12px">物流事件</label><div style="margin-top:8px">${(data.events || []).map(e => `<div style="padding:6px 0;border-bottom:1px solid var(--line);font-size:12px"><span style="color:var(--accent)">${e.time || e.timestamp || ''}</span> ${e.description || e.message || ''}</div>`).join('')}</div></div>` : ''}
      </div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim)">查询失败，请检查追踪号</div>';
  }
};
