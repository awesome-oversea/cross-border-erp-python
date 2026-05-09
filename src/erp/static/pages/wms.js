import api from '../js/api.js';
import { formatNumber, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>库存控制塔</h2><p>事务账、可售、预占、在途和库龄</p></div>
    </div>
    <div class="panel">
      <div class="metric-grid" id="wmsMetrics">${loadingSpinner()}</div>
    </div>
    <div class="panel">
      <div class="filter-bar">
        <input id="wmsSkuFilter" class="form-input" placeholder="SKU 编码" style="min-width:160px">
        <select id="wmsWarehouseFilter" class="form-input" style="min-width:140px">
          <option value="">全部仓库</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadInventory()">查询</button>
      </div>
      <div id="wmsInventoryTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadInventory(); };
  loadMetrics();
  loadInventory();
  loadWarehouses();
}

async function loadMetrics() {
  const el = document.getElementById('wmsMetrics');
  try {
    const res = await api.get('/api/wms/v1/inventory/summary');
    const d = res.data || {};
    el.innerHTML = `
      <div class="metric-tile"><strong style="color:var(--sky)">${formatNumber(d.total_quantity || 0)}</strong><span>库存总量</span></div>
      <div class="metric-tile"><strong style="color:var(--mint)">${formatNumber(d.available_quantity || 0)}</strong><span>可售数量</span></div>
      <div class="metric-tile"><strong style="color:var(--amber)">${formatNumber(d.reserved_quantity || 0)}</strong><span>预占数量</span></div>
      <div class="metric-tile"><strong style="color:var(--rose)">${formatNumber(d.low_stock_count || 0)}</strong><span>低库存 SKU</span></div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim);padding:24px;text-align:center">指标加载失败</div>';
  }
}

async function loadWarehouses() {
  try {
    const res = await api.get('/api/wms/v1/warehouses', { page: 1, page_size: 100 });
    const warehouses = res.data?.items || res.data || [];
    const sel = document.getElementById('wmsWarehouseFilter');
    warehouses.forEach(w => {
      const opt = document.createElement('option');
      opt.value = w.id || w.code;
      opt.textContent = w.name || w.code;
      sel.appendChild(opt);
    });
  } catch {}
}

async function loadInventory() {
  const el = document.getElementById('wmsInventoryTable');
  const sku = document.getElementById('wmsSkuFilter')?.value || '';
  const warehouseId = document.getElementById('wmsWarehouseFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (sku) params.sku_code = sku;
    if (warehouseId) params.warehouse_id = warehouseId;
    const res = await api.get('/api/wms/v1/inventory', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: 'SKU', key: 'sku_code' },
      { label: '仓库', key: 'warehouse_name', render: r => r.warehouse_name || '-' },
      { label: '总量', key: 'quantity', render: r => formatNumber(r.quantity) },
      { label: '可售', key: 'available_quantity', render: r => formatNumber(r.available_quantity) },
      { label: '预占', key: 'reserved_quantity', render: r => formatNumber(r.reserved_quantity) },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">库存数据加载失败</div>';
  }
}

window.erpLoadInventory = loadInventory;
