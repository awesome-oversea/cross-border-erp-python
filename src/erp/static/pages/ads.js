import api from '../js/api.js';
import { formatCurrency, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>广告管理</h2><p>广告投放、智能出价、ROI 分析</p></div>
    </div>
    <div class="panel">
      <div class="filter-bar">
        <select id="adsPlatformFilter" class="form-input" style="min-width:120px">
          <option value="">全部平台</option>
          <option value="amazon">Amazon</option>
          <option value="shopee">Shopee</option>
          <option value="tiktok">TikTok</option>
        </select>
        <select id="adsStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="active">投放中</option>
          <option value="paused">已暂停</option>
          <option value="completed">已结束</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadCampaigns()">查询</button>
      </div>
      <div id="adsCampaignTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadCampaigns(); };
  loadCampaigns();
}

async function loadCampaigns() {
  const el = document.getElementById('adsCampaignTable');
  const platform = document.getElementById('adsPlatformFilter')?.value || '';
  const status = document.getElementById('adsStatusFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (platform) params.platform = platform;
    if (status) params.status = status;
    const res = await api.get('/api/ads/v1/campaigns', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: '广告活动', key: 'campaign_name', render: r => r.campaign_name || '-' },
      { label: '平台', key: 'platform', render: r => r.platform || '-' },
      { label: '预算', key: 'daily_budget', render: r => formatCurrency(r.daily_budget) },
      { label: '花费', key: 'spend', render: r => formatCurrency(r.spend) },
      { label: 'ACoS', key: 'acos', render: r => r.acos ? `${(r.acos * 100).toFixed(1)}%` : '-' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">广告数据加载失败</div>';
  }
}

window.erpLoadCampaigns = loadCampaigns;
