import api from '../js/api.js';
import { formatNumber, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>FBA / 海外仓</h2><p>FBA 库存同步、补货建议、货件管理</p></div>
    </div>
    <div class="panel">
      <div class="metric-grid" id="fbaMetrics">${loadingSpinner()}</div>
    </div>
    <div class="panel">
      <div class="panel-header"><div><h3>FBA 库存</h3><p>亚马逊 FBA 库存概况</p></div></div>
      <div id="fbaInventoryTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadFBAInventory(); };
  loadMetrics();
  loadFBAInventory();
}

async function loadMetrics() {
  const el = document.getElementById('fbaMetrics');
  try {
    const res = await api.get('/api/fba/v1/shipments', { page: 1, page_size: 1 });
    const total = res.data?.total || 0;
    el.innerHTML = `
      <div class="metric-tile"><strong style="color:var(--sky)">${total}</strong><span>货件总数</span></div>
      <div class="metric-tile"><strong style="color:var(--mint)">-</strong><span>在途货件</span></div>
      <div class="metric-tile"><strong style="color:var(--amber)">-</strong><span>待补货 SKU</span></div>
      <div class="metric-tile"><strong style="color:var(--accent)">-</strong><span>低库存预警</span></div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim);padding:24px;text-align:center">指标加载失败</div>';
  }
}

async function loadFBAInventory() {
  const el = document.getElementById('fbaInventoryTable');
  try {
    const res = await api.get('/api/fba/v1/inventory', { page: currentPage, page_size: PAGE_SIZE });
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: 'SKU', key: 'sku_code', render: r => r.sku_code || '-' },
      { label: 'FNSKU', key: 'fnsku', render: r => r.fnsku || '-' },
      { label: '可售数量', key: 'fulfillable_quantity', render: r => formatNumber(r.fulfillable_quantity) },
      { label: '在途数量', key: 'inbound_quantity', render: r => formatNumber(r.inbound_quantity) },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">FBA 库存数据加载失败</div>';
  }
}
