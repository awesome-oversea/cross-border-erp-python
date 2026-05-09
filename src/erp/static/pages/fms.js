import api from '../js/api.js';
import { formatCurrency, formatDateTime, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>结算与利润</h2><p>结算单管理、成本核算、利润分析</p></div>
    </div>
    <div class="panel">
      <div class="metric-grid" id="fmsMetrics">${loadingSpinner()}</div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div><h3>结算单</h3><p>渠道结算与对账</p></div>
      </div>
      <div class="filter-bar">
        <select id="fmsSettleStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="pending">待结算</option>
          <option value="processing">处理中</option>
          <option value="completed">已完成</option>
          <option value="disputed">有争议</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadSettlements()">查询</button>
      </div>
      <div id="fmsSettlementTable">${loadingSpinner()}</div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div><h3>凭证管理</h3><p>财务凭证与账务记录</p></div>
      </div>
      <div id="fmsVoucherTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadSettlements(); };
  loadMetrics();
  loadSettlements();
  loadVouchers();
}

async function loadMetrics() {
  const el = document.getElementById('fmsMetrics');
  try {
    const res = await api.get('/api/fms/v1/settlements', { page: 1, page_size: 1 });
    const total = res.data?.total || 0;
    el.innerHTML = `
      <div class="metric-tile"><strong style="color:var(--sky)">${total}</strong><span>结算单总数</span></div>
      <div class="metric-tile"><strong style="color:var(--accent)">-</strong><span>待结算金额</span></div>
      <div class="metric-tile"><strong style="color:var(--mint)">-</strong><span>本月利润</span></div>
      <div class="metric-tile"><strong style="color:var(--amber)">-</strong><span>利润率</span></div>
    `;
  } catch {
    el.innerHTML = '<div style="color:var(--dim);padding:24px;text-align:center">指标加载失败</div>';
  }
}

async function loadSettlements() {
  const el = document.getElementById('fmsSettlementTable');
  const status = document.getElementById('fmsSettleStatusFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (status) params.status = status;
    const res = await api.get('/api/fms/v1/settlements', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: '结算单号', key: 'settlement_no' },
      { label: '渠道', key: 'platform', render: r => r.platform || '-' },
      { label: '金额', key: 'amount', render: r => formatCurrency(r.amount) },
      { label: '币种', key: 'currency', render: r => r.currency || 'CNY' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '结算周期', key: 'period', render: r => r.period || '-' },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">结算数据加载失败</div>';
  }
}

async function loadVouchers() {
  const el = document.getElementById('fmsVoucherTable');
  try {
    const res = await api.get('/api/fms/v1/vouchers', { page: 1, page_size: 10 });
    const items = res.data?.items || [];
    if (!items.length) {
      el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">暂无凭证</div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '凭证号', key: 'voucher_no' },
      { label: '类型', key: 'voucher_type', render: r => r.voucher_type || '-' },
      { label: '金额', key: 'amount', render: r => formatCurrency(r.amount) },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
    ], items);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">凭证数据加载失败</div>';
  }
}

window.erpLoadSettlements = loadSettlements;
