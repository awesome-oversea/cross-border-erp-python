import api from '../js/api.js';
import { formatCurrency, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>商品中心</h2><p>SPU / SKU / 分类 / 品牌管理</p></div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-primary btn-sm" onclick="erpShowCreateSPU()">+ 新建 SPU</button>
        <button class="btn btn-ghost btn-sm" onclick="erpShowCreateSKU()">+ 新建 SKU</button>
      </div>
    </div>

    <div class="panel">
      <div class="filter-bar">
        <select id="pdmStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="pending_review">待审核</option>
          <option value="approved">已审核</option>
          <option value="listed">已上架</option>
          <option value="delisted">已下架</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadSPUs()">查询</button>
      </div>
      <div id="pdmSpuTable">${loadingSpinner()}</div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div><h3>分类管理</h3><p>产品分类树形结构</p></div>
      </div>
      <div id="pdmCategoryTree">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadSPUs(); };
  loadSPUs();
  loadCategories();
}

async function loadSPUs() {
  const el = document.getElementById('pdmSpuTable');
  const status = document.getElementById('pdmStatusFilter')?.value || '';
  try {
    const res = await api.get('/api/pdm/v1/spus', { page: currentPage, page_size: PAGE_SIZE, status });
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: 'SPU 编码', key: 'code' },
      { label: '名称', key: 'name' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '分类', key: 'category_id', render: r => r.category_id ? r.category_id.slice(0, 8) + '...' : '-' },
    ], items, {
      actions: (r) => `<button class="btn btn-ghost btn-sm" onclick="erpViewSPU('${r.id}')">详情</button>`,
    }) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">数据加载失败</div>';
  }
}

async function loadCategories() {
  const el = document.getElementById('pdmCategoryTree');
  try {
    const res = await api.get('/api/pdm/v1/categories');
    const tree = res.data || [];
    if (!tree.length) {
      el.innerHTML = '<div class="empty-state"><h3>暂无分类</h3></div>';
      return;
    }
    el.innerHTML = tree.map(c => `
      <div style="padding:8px 12px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:8px;padding-left:${(c.level || 1) * 20 + 12}px">
        <span style="color:var(--accent);font-size:12px">${c.level > 1 ? '└' : '●'}</span>
        <span style="font-weight:600;font-size:13px">${c.name}</span>
        <span style="color:var(--dim);font-size:11px;font-family:var(--mono)">${c.code}</span>
      </div>
    `).join('');
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">分类加载失败</div>';
  }
}

window.erpLoadSPUs = loadSPUs;

window.erpViewSPU = async function(id) {
  try {
    const res = await api.get(`/api/pdm/v1/spus/${id}`);
    const spu = res.data;
    if (!spu) { alert('SPU 不存在'); return; }
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    modal.innerHTML = `
      <div class="modal">
        <h3>SPU 详情</h3>
        <div style="display:grid;gap:12px">
          <div><label style="color:var(--dim);font-size:12px">编码</label><div style="font-family:var(--mono)">${spu.code}</div></div>
          <div><label style="color:var(--dim);font-size:12px">名称</label><div>${spu.name}</div></div>
          <div><label style="color:var(--dim);font-size:12px">状态</label><div>${statusBadge(spu.status)}</div></div>
          <div><label style="color:var(--dim);font-size:12px">属性</label><div style="font-size:12px;color:var(--muted)">${JSON.stringify(spu.attributes || {}, null, 2)}</div></div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  } catch { alert('加载失败'); }
};

window.erpShowCreateSPU = function() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  modal.innerHTML = `
    <div class="modal">
      <h3>新建 SPU</h3>
      <form id="createSPUForm">
        <div class="form-group"><label>名称</label><input class="form-input" name="name" required></div>
        <div class="form-group"><label>编码</label><input class="form-input" name="code" required></div>
        <div class="form-group"><label>英文名</label><input class="form-input" name="name_en"></div>
        <div class="form-group"><label>原产国</label><input class="form-input" name="origin_country" value="CN"></div>
        <div class="form-group"><label>申报价值</label><input class="form-input" name="declared_value" type="number" step="0.01" value="0"></div>
      </form>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">取消</button>
        <button class="btn btn-primary" onclick="erpSubmitCreateSPU()">创建</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
};

window.erpSubmitCreateSPU = async function() {
  const form = document.getElementById('createSPUForm');
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  body.declared_value = parseFloat(body.declared_value) || 0;
  body.images = [];
  body.attributes = {};
  try {
    await api.post('/api/pdm/v1/spus', body);
    document.querySelector('.modal-overlay')?.remove();
    loadSPUs();
  } catch (e) { alert('创建失败: ' + (e.message || '未知错误')); }
};

window.erpShowCreateSKU = function() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  modal.innerHTML = `
    <div class="modal">
      <h3>新建 SKU</h3>
      <form id="createSKUForm">
        <div class="form-group"><label>SPU ID</label><input class="form-input" name="spu_id" required></div>
        <div class="form-group"><label>SKU 编码</label><input class="form-input" name="sku_code" required></div>
        <div class="form-group"><label>名称</label><input class="form-input" name="name"></div>
        <div class="form-group"><label>重量(kg)</label><input class="form-input" name="weight" type="number" step="0.01" value="0"></div>
        <div class="form-group"><label>成本价</label><input class="form-input" name="cost_price" type="number" step="0.01" value="0"></div>
      </form>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">取消</button>
        <button class="btn btn-primary" onclick="erpSubmitCreateSKU()">创建</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
};

window.erpSubmitCreateSKU = async function() {
  const form = document.getElementById('createSKUForm');
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  body.weight = parseFloat(body.weight) || 0;
  body.cost_price = parseFloat(body.cost_price) || 0;
  body.length = 0; body.width = 0; body.height = 0;
  body.purchase_price = 0;
  body.variant_attrs = {}; body.spec = {};
  try {
    await api.post('/api/pdm/v1/skus', body);
    document.querySelector('.modal-overlay')?.remove();
    loadSPUs();
  } catch (e) { alert('创建失败: ' + (e.message || '未知错误')); }
};
