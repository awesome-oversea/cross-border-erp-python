function formatNumber(n, decimals = 0) {
  if (n == null) return '-';
  return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatCurrency(n, currency = 'CNY') {
  if (n == null) return '-';
  const symbols = { CNY: '¥', USD: '$', EUR: '€', GBP: '£', JPY: '¥' };
  return `${symbols[currency] || currency} ${formatNumber(n, 2)}`;
}

function formatDate(d) {
  if (!d) return '-';
  return new Date(d).toLocaleDateString('zh-CN');
}

function formatDateTime(d) {
  if (!d) return '-';
  return new Date(d).toLocaleString('zh-CN');
}

function statusBadge(status, map = {}) {
  const colors = {
    active: '#55d487', approved: '#55d487', completed: '#55d487', resolved: '#55d487',
    listed: '#55d487', delivered: '#55d487', closed: '#55d487', available: '#55d487',
    pending: '#f0c96d', pending_review: '#f0c96d', draft: '#f0c96d', in_progress: '#7aaef5',
    processing: '#7aaef5', shipped: '#7aaef5', allocated: '#7aaef5',
    cancelled: '#7d756d', discontinued: '#7d756d', rejected: '#ff7676',
    failed: '#ff7676', error: '#ff7676', locked: '#ff7676', escalated: '#ff7676',
    ...map,
  };
  const color = colors[status] || '#7d756d';
  return `<span style="display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;color:${color};background:${color}18;border:1px solid ${color}30">${status}</span>`;
}

function buildTable(columns, rows, opts = {}) {
  if (!rows || rows.length === 0) {
    return `<div style="text-align:center;padding:48px 0;color:var(--muted)">暂无数据</div>`;
  }
  let html = '<table class="data-table"><thead><tr>';
  for (const col of columns) {
    html += `<th>${col.label}</th>`;
  }
  if (opts.actions) html += '<th style="width:120px">操作</th>';
  html += '</tr></thead><tbody>';
  for (const row of rows) {
    html += '<tr>';
    for (const col of columns) {
      const val = col.render ? col.render(row) : (row[col.key] ?? '-');
      html += `<td>${val}</td>`;
    }
    if (opts.actions) {
      html += `<td>${opts.actions(row)}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  return html;
}

function buildPagination(total, page, pageSize) {
  const totalPages = Math.ceil(total / pageSize) || 1;
  if (totalPages <= 1) return '';
  let html = '<div class="pagination">';
  html += `<span class="pg-info">共 ${total} 条 / ${totalPages} 页</span>`;
  html += `<button class="pg-btn" onclick="erpPaginate(${page - 1})" ${page <= 1 ? 'disabled' : ''}>‹</button>`;
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, page + 2);
  for (let i = start; i <= end; i++) {
    html += `<button class="pg-btn ${i === page ? 'active' : ''}" onclick="erpPaginate(${i})">${i}</button>`;
  }
  html += `<button class="pg-btn" onclick="erpPaginate(${page + 1})" ${page >= totalPages ? 'disabled' : ''}>›</button>`;
  html += '</div>';
  return html;
}

window.erpPaginate = function(p) {
  if (p < 1) return;
  if (window.__erpCurrentPageFn) window.__erpCurrentPageFn(p);
};

function loadingSpinner() {
  return '<div class="loading-spinner"><div class="spinner"></div><span>加载中...</span></div>';
}

export { formatNumber, formatCurrency, formatDate, formatDateTime, statusBadge, buildTable, buildPagination, loadingSpinner };
