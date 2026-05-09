import api from '../js/api.js';
import { formatCurrency, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>采购与供应链</h2><p>供应商管理、采购单、到货质检</p></div>
      <button class="btn btn-primary btn-sm" onclick="erpShowCreatePO()">+ 新建采购单</button>
    </div>
    <div class="grid-2">
      <div class="panel">
        <div class="panel-header"><div><h3>供应商概况</h3><p>已注册供应商和评级分布</p></div></div>
        <div id="scmSupplierSummary">${loadingSpinner()}</div>
      </div>
      <div class="panel">
        <div class="panel-header"><div><h3>采购统计</h3><p>近期采购单状态分布</p></div></div>
        <div id="scmPOStats">${loadingSpinner()}</div>
      </div>
    </div>
    <div class="panel">
      <div class="filter-bar">
        <select id="scmPOStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="submitted">已提交</option>
          <option value="confirmed">已确认</option>
          <option value="partial_received">部分到货</option>
          <option value="completed">已完成</option>
          <option value="cancelled">已取消</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadPOs()">查询</button>
      </div>
      <div id="scmPOTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadPOs(); };
  loadSupplierSummary();
  loadPOStats();
  loadPOs();
}

async function loadSupplierSummary() {
  const el = document.getElementById('scmSupplierSummary');
  try {
    const res = await api.get('/api/scm/v1/suppliers', { page: 1, page_size: 1 });
    const total = res.data?.total || 0;
    el.innerHTML = `
      <div class="metric-grid">
        <div class="metric-tile"><strong style="color:var(--sky)">${total}</strong><span>供应商总数</span></div>
        <div class="metric-tile"><strong style="color:var(--mint)">-</strong><span>优质供应商</span></div>
      </div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim);text-align:center;padding:24px">加载失败</div>';
  }
}

async function loadPOStats() {
  const el = document.getElementById('scmPOStats');
  try {
    const res = await api.get('/api/scm/v1/purchase-orders', { page: 1, page_size: 1 });
    const total = res.data?.total || 0;
    el.innerHTML = `
      <div class="metric-grid">
        <div class="metric-tile"><strong style="color:var(--accent)">${total}</strong><span>采购单总数</span></div>
        <div class="metric-tile"><strong style="color:var(--amber)">-</strong><span>待处理</span></div>
      </div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim);text-align:center;padding:24px">加载失败</div>';
  }
}

async function loadPOs() {
  const el = document.getElementById('scmPOTable');
  const status = document.getElementById('scmPOStatusFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (status) params.status = status;
    const res = await api.get('/api/scm/v1/purchase-orders', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: '采购单号', key: 'po_no' },
      { label: '供应商', key: 'supplier_name', render: r => r.supplier_name || '-' },
      { label: '金额', key: 'total_amount', render: r => formatCurrency(r.total_amount) },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '创建时间', key: 'created_at', render: r => r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : '-' },
    ], items, {
      actions: (r) => `<button class="btn btn-ghost btn-sm" onclick="erpViewPO('${r.id}')">详情</button>`,
    }) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">采购单数据加载失败</div>';
  }
}

window.erpLoadPOs = loadPOs;

window.erpViewPO = async function(id) {
  try {
    const res = await api.get(`/api/scm/v1/purchase-orders/${id}`);
    const po = res.data;
    if (!po) { alert('采购单不存在'); return; }
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    modal.innerHTML = `
      <div class="modal">
        <h3>采购单详情</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div><label style="color:var(--dim);font-size:12px">单号</label><div style="font-family:var(--mono)">${po.po_no}</div></div>
          <div><label style="color:var(--dim);font-size:12px">供应商</label><div>${po.supplier_name || '-'}</div></div>
          <div><label style="color:var(--dim);font-size:12px">金额</label><div>${formatCurrency(po.total_amount)}</div></div>
          <div><label style="color:var(--dim);font-size:12px">状态</label><div>${statusBadge(po.status)}</div></div>
        </div>
        <div class="modal-actions"><button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">关闭</button></div>
      </div>
    `;
    document.body.appendChild(modal);
  } catch { alert('加载失败'); }
};

window.erpShowCreatePO = function() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  modal.innerHTML = `
    <div class="modal">
      <h3>新建采购单</h3>
      <form id="createPOForm">
        <div class="form-group"><label>供应商 ID</label><input class="form-input" name="supplier_id" required></div>
        <div class="form-group"><label>备注</label><textarea class="form-input" name="remark" rows="3"></textarea></div>
      </form>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">取消</button>
        <button class="btn btn-primary" onclick="erpSubmitCreatePO()">创建</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
};

window.erpSubmitCreatePO = async function() {
  const form = document.getElementById('createPOForm');
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  body.items = [];
  try {
    await api.post('/api/scm/v1/purchase-orders', body);
    document.querySelector('.modal-overlay')?.remove();
    loadPOs();
  } catch (e) { alert('创建失败: ' + (e.message || '未知错误')); }
};
