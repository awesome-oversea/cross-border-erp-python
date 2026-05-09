import api from '../js/api.js';
import { statusBadge, buildTable, buildPagination, loadingSpinner } from '../js/utils.js';

let currentPage = 1;
const PAGE_SIZE = 20;

export function render() {
  const content = document.getElementById('page-content');
  content.innerHTML = `
    <div class="page-header">
      <div><h2>系统设置</h2><p>参数配置、审批流程、数据管理</p></div>
    </div>
    <div class="grid-2">
      <div class="panel">
        <div class="panel-header"><div><h3>系统参数</h3><p>全局参数配置</p></div></div>
        <div id="sysParamTable">${loadingSpinner()}</div>
      </div>
      <div class="panel">
        <div class="panel-header"><div><h3>审批流程</h3><p>待审批事项</p></div></div>
        <div id="sysApprovalTable">${loadingSpinner()}</div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-header"><div><h3>连接器管理</h3><p>平台连接器配置与状态</p></div></div>
      <div id="sysConnectorTable">${loadingSpinner()}</div>
    </div>
  `;

  window.__erpCurrentPageFn = (p) => { currentPage = p; loadParams(); };
  loadParams();
  loadApprovals();
  loadConnectors();
}

async function loadParams() {
  const el = document.getElementById('sysParamTable');
  try {
    const res = await api.get('/api/sys/v1/params', { page: currentPage, page_size: PAGE_SIZE });
    const items = res.data?.items || [];
    const total = res.data?.total || 0;
    el.innerHTML = buildTable([
      { label: '参数键', key: 'param_key' },
      { label: '参数值', key: 'param_value', render: r => (r.param_value || '-').slice(0, 40) },
      { label: '描述', key: 'description', render: r => (r.description || '-').slice(0, 30) },
    ], items) + buildPagination(total, currentPage, PAGE_SIZE);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:32px;color:var(--dim)">参数数据加载失败</div>';
  }
}

async function loadApprovals() {
  const el = document.getElementById('sysApprovalTable');
  try {
    const res = await api.get('/api/sys/v1/approvals', { page: 1, page_size: 10 });
    const items = res.data?.items || [];
    if (!items.length) {
      el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--mint)">✓ 暂无待审批事项</div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '审批号', key: 'approval_no' },
      { label: '类型', key: 'approval_type', render: r => r.approval_type || '-' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status) },
      { label: '申请人', key: 'applicant', render: r => r.applicant || '-' },
    ], items);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">审批数据加载失败</div>';
  }
}

async function loadConnectors() {
  const el = document.getElementById('sysConnectorTable');
  try {
    const res = await api.get('/api/sys/v1/connectors', { page: 1, page_size: 20 });
    const items = res.data?.items || [];
    if (!items.length) {
      el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">暂无连接器</div>';
      return;
    }
    el.innerHTML = buildTable([
      { label: '名称', key: 'name' },
      { label: '平台', key: 'platform', render: r => r.platform || '-' },
      { label: '类型', key: 'connector_type', render: r => r.connector_type || '-' },
      { label: '状态', key: 'status', render: r => statusBadge(r.status, { connected: '#55d487', disconnected: '#ff7676' }) },
    ], items);
  } catch {
    el.innerHTML = '<div style="text-align:center;padding:24px;color:var(--dim)">连接器数据加载失败</div>';
  }
}
