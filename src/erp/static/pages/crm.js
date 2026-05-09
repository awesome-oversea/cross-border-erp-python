import api from '../js/api.js';
import { formatCurrency, formatDateTime, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>售后中心</h2><p>退货退款、投诉工单、客户管理</p></div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div><h3>退货退款</h3><p>退货申请与退款处理</p></div>
      </div>
      <div class="filter-bar">
        <select id="crmReturnStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="approved">已批准</option>
          <option value="rejected">已拒绝</option>
          <option value="processing">处理中</option>
          <option value="completed">已完成</option>
        </select>
        <button class="btn btn-ghost btn-sm" onclick="erpLoadReturns()">查询</button>
      </div>
      <div id="crmReturnTable">${loadingSpinner()}</div>
    </div>
    <div class="panel">
      <div class="panel-header">
        <div><h3>投诉工单</h3><p>客户投诉与纠纷处理</p></div>
      </div>
      <div id="crmComplaintTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadReturns(); };
  loadReturns();
  loadComplaints();
}

async function loadReturns() {
  const el = document.getElementById('crmReturnTable');
  const status = document.getElementById('crmReturnStatusFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (status) params.status = status;
    const res = await api.get('/api/crm/v1/returns', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: '退货单号', key: 'return_no' },
      { label: '类型', key: 'return_type', render: r => r.return_type || '-' },
      { label: '数量', key: 'quantity', render: r => r.quantity || '-' },
      { label: '退款金额', key: 'refund_amount', render: r => formatCurrency(r.refund_amount) },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">退货数据加载失败</div>';
  }
}

async function loadComplaints() {
  const el = document.getElementById('crmComplaintTable');
  try {
    const res = await api.get('/api/crm/v1/complaints', { page: 1, page_size: 10 });
    const items = res.data?.items || [];
    if (!items.length) {
      el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">暂无投诉工单</div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '工单号', key: 'complaint_no' },
      { label: '类型', key: 'complaint_type', render: r => r.complaint_type || '-' },
      { label: '严重程度', key: 'severity', render: r => statusBadge(r.severity, { high: '#ff7676', medium: '#f0c96d', low: '#55d487' }) },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '主题', key: 'subject', render: r => (r.subject || '-').slice(0, 30) },
    ], items);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">投诉数据加载失败</div>';
  }
}

window.erpLoadReturns = loadReturns;
