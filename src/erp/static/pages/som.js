import api from '../js/api.js';
import { statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>渠道运营</h2><p>店铺管理、Listing 发布、价格策略</p></div>
      <button class="btn btn-primary btn-sm" onclick="erpShowCreateListing()">+ 新建 Listing</button>
    </div>
    <div class="panel">
      <div class="filter-bar">
        <select id="somPlatformFilter" class="form-input" style="min-width:120px">
          <option value="">全部平台</option>
          <option value="amazon">Amazon</option>
          <option value="shopee">Shopee</option>
          <option value="lazada">Lazada</option>
          <option value="tiktok">TikTok</option>
          <option value="temu">Temu</option>
        </select>
        <select id="somStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="pending_review">待审核</option>
          <option value="published">已发布</option>
          <option value="delisted">已下架</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadListings()">查询</button>
      </div>
      <div id="somListingTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadListings(); };
  loadListings();
}

async function loadListings() {
  const el = document.getElementById('somListingTable');
  const platform = document.getElementById('somPlatformFilter')?.value || '';
  const status = document.getElementById('somStatusFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (platform) params.platform = platform;
    if (status) params.status = status;
    const res = await api.get('/api/som/v1/listings', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: 'Listing ID', key: 'listing_id', render: r => r.listing_id || r.id || '-' },
      { label: 'SPU', key: 'spu_code', render: r => r.spu_code || '-' },
      { label: '平台', key: 'platform', render: r => r.platform || '-' },
      { label: '店铺', key: 'store_name', render: r => r.store_name || '-' },
      { label: '标题', key: 'title', render: r => (r.title || '-').slice(0, 40) },
      { label: '价格', key: 'price', render: r => r.price ? `${r.currency || '$'} ${r.price}` : '-' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">Listing 数据加载失败</div>';
  }
}

window.erpLoadListings = loadListings;

window.erpShowCreateListing = function() {
  const modal = document.createElement('div');
  modal.className = 'modal-overlay';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
  modal.innerHTML = `
    <div class="modal">
      <h3>新建 Listing</h3>
      <form id="createListingForm">
        <div class="form-group"><label>SPU ID</label><input class="form-input" name="spu_id" required></div>
        <div class="form-group"><label>平台</label>
          <select class="form-input" name="platform">
            <option value="amazon">Amazon</option>
            <option value="shopee">Shopee</option>
            <option value="lazada">Lazada</option>
            <option value="tiktok">TikTok</option>
            <option value="temu">Temu</option>
          </select>
        </div>
        <div class="form-group"><label>店铺 ID</label><input class="form-input" name="store_id"></div>
        <div class="form-group"><label>标题</label><input class="form-input" name="title" required></div>
        <div class="form-group"><label>价格</label><input class="form-input" name="price" type="number" step="0.01" value="0"></div>
      </form>
      <div class="modal-actions">
        <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">取消</button>
        <button class="btn btn-primary" onclick="erpSubmitCreateListing()">创建</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
};

window.erpSubmitCreateListing = async function() {
  const form = document.getElementById('createListingForm');
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  body.price = parseFloat(body.price) || 0;
  try {
    await api.post('/api/som/v1/listings', body);
    document.querySelector('.modal-overlay')?.remove();
    loadListings();
  } catch (e) { alert('创建失败: ' + (e.message || '未知错误')); }
};
