import api from '../js/api.js';
import { formatCurrency, formatDateTime, statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>订单中心</h2><p>渠道订单、ERP 销售单、异常单处理</p></div>
    </div>

    <div class="panel">
      <div class="filter-bar">
        <select id="omsStatusFilter" class="form-input" style="min-width:120px">
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="confirmed">已确认</option>
          <option value="processing">处理中</option>
          <option value="shipped">已发货</option>
          <option value="delivered">已签收</option>
          <option value="cancelled">已取消</option>
        </select>
        <input id="omsOrderNoFilter" class="form-input" placeholder="订单号" style="min-width:160px">
        <button class="btn btn-ghost btn-sm" onclick="erpLoadOrders()">查询</button>
      </div>
      <div id="omsOrderTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadOrders(); };
  loadOrders();
}

async function loadOrders() {
  const el = document.getElementById('omsOrderTable');
  const status = document.getElementById('omsStatusFilter')?.value || '';
  const orderNo = document.getElementById('omsOrderNoFilter')?.value || '';
  try {
    const params = { page: currentPage, page_size: PAGE_SIZE };
    if (status) params.status = status;
    if (orderNo) params.order_no = orderNo;
    const res = await api.get('/api/oms/v1/orders', params);
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: '订单号', key: 'order_no' },
      { label: '平台', key: 'platform', render: r => r.platform || '-' },
      { label: '店铺', key: 'store_name', render: r => r.store_name || '-' },
      { label: '金额', key: 'total_amount', render: r => formatCurrency(r.total_amount, r.currency || 'CNY') },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '下单时间', key: 'order_date', render: r => formatDateTime(r.order_date) },
    ], items, {
      actions: (r) => `<button class="btn btn-ghost btn-sm" onclick="erpViewOrder('${r.id}')">详情</button>`,
    }) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">订单数据加载失败</div>';
  }
}

window.erpLoadOrders = loadOrders;

window.erpViewOrder = async function(id) {
  try {
    const res = await api.get(`/api/oms/v1/orders/${id}`);
    const order = res.data;
    if (!order) { alert('订单不存在'); return; }
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
    modal.innerHTML = `
      <div class="modal" style="max-width:640px">
        <h3>订单详情</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div><label style="color:var(--dim);font-size:12px">订单号</label><div style="font-family:var(--mono)">${order.order_no}</div></div>
          <div><label style="color:var(--dim);font-size:12px">平台</label><div>${order.platform || '-'}</div></div>
          <div><label style="color:var(--dim);font-size:12px">金额</label><div>${formatCurrency(order.total_amount, order.currency || 'CNY')}</div></div>
          <div><label style="color:var(--dim);font-size:12px">状态</label><div>${statusBadge(order.status)}</div></div>
          <div><label style="color:var(--dim);font-size:12px">买家</label><div>${order.buyer_name || '-'}</div></div>
          <div><label style="color:var(--dim);font-size:12px">收货地址</label><div style="font-size:12px">${order.shipping_address || '-'}</div></div>
        </div>
        ${order.items ? `<div style="margin-top:16px"><label style="color:var(--dim);font-size:12px">商品明细</label><div style="margin-top:8px;font-size:12px;color:var(--muted)">${JSON.stringify(order.items, null, 2)}</div></div>` : ''}
        <div class="modal-actions">
          <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">关闭</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  } catch { alert('加载失败'); }
};
