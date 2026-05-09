import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/dashboard/Index.vue'), meta: { title: '工作台', icon: 'Monitor' } },
      { path: 'iam/users', name: 'IAMUsers', component: () => import('@/views/iam/Users.vue'), meta: { title: '用户管理', domain: 'IAM' } },
      { path: 'iam/roles', name: 'IAMRoles', component: () => import('@/views/iam/Roles.vue'), meta: { title: '角色权限', domain: 'IAM' } },
      { path: 'iam/orgs', name: 'IAMOrgs', component: () => import('@/views/iam/Organizations.vue'), meta: { title: '组织管理', domain: 'IAM' } },
      { path: 'pdm/spus', name: 'PDMSPUs', component: () => import('@/views/pdm/SPUs.vue'), meta: { title: 'SPU管理', domain: 'PDM' } },
      { path: 'pdm/skus', name: 'PDMSKUs', component: () => import('@/views/pdm/SKUs.vue'), meta: { title: 'SKU管理', domain: 'PDM' } },
      { path: 'pdm/compliance', name: 'PDMCompliance', component: () => import('@/views/pdm/Compliance.vue'), meta: { title: '合规检查', domain: 'PDM' } },
      { path: 'som/stores', name: 'SOMStores', component: () => import('@/views/som/Stores.vue'), meta: { title: '店铺管理', domain: 'SOM' } },
      { path: 'som/listings', name: 'SOMListings', component: () => import('@/views/som/Listings.vue'), meta: { title: 'Listing管理', domain: 'SOM' } },
      { path: 'som/pricing', name: 'SOMPricing', component: () => import('@/views/som/Pricing.vue'), meta: { title: '自动定价', domain: 'SOM' } },
      { path: 'oms/orders', name: 'OMSOrders', component: () => import('@/views/oms/Orders.vue'), meta: { title: '订单管理', domain: 'OMS' } },
      { path: 'oms/orders/:id', name: 'OMSOrderDetail', component: () => import('@/views/oms/OrderDetail.vue'), meta: { title: '订单详情', domain: 'OMS' } },
      { path: 'oms/refunds', name: 'OMSRefunds', component: () => import('@/views/oms/Refunds.vue'), meta: { title: '退款管理', domain: 'OMS' } },
      { path: 'scm/purchase-orders', name: 'SCMPurchaseOrders', component: () => import('@/views/scm/PurchaseOrders.vue'), meta: { title: '采购订单', domain: 'SCM' } },
      { path: 'scm/suppliers', name: 'SCMSuppliers', component: () => import('@/views/scm/Suppliers.vue'), meta: { title: '供应商管理', domain: 'SCM' } },
      { path: 'scm/inquiries', name: 'SCMInquiries', component: () => import('@/views/scm/Inquiries.vue'), meta: { title: '询价管理', domain: 'SCM' } },
      { path: 'wms/inventory', name: 'WMSInventory', component: () => import('@/views/wms/Inventory.vue'), meta: { title: '库存管理', domain: 'WMS' } },
      { path: 'wms/inbound', name: 'WMSInbound', component: () => import('@/views/wms/Inbound.vue'), meta: { title: '入库管理', domain: 'WMS' } },
      { path: 'wms/outbound', name: 'WMSOutbound', component: () => import('@/views/wms/Outbound.vue'), meta: { title: '出库管理', domain: 'WMS' } },
      { path: 'wms/alerts', name: 'WMSAlerts', component: () => import('@/views/wms/Alerts.vue'), meta: { title: '库存预警', domain: 'WMS' } },
      { path: 'tms/shipments', name: 'TMSShipments', component: () => import('@/views/tms/Shipments.vue'), meta: { title: '物流管理', domain: 'TMS' } },
      { path: 'tms/tracking', name: 'TMSTracking', component: () => import('@/views/tms/Tracking.vue'), meta: { title: '物流追踪', domain: 'TMS' } },
      { path: 'tms/freight', name: 'TMSFreight', component: () => import('@/views/tms/Freight.vue'), meta: { title: '运费管理', domain: 'TMS' } },
      { path: 'fms/settlements', name: 'FMSSettlements', component: () => import('@/views/fms/Settlements.vue'), meta: { title: '结算管理', domain: 'FMS' } },
      { path: 'fms/profit', name: 'FMSProfit', component: () => import('@/views/fms/Profit.vue'), meta: { title: '利润分析', domain: 'FMS' } },
      { path: 'fms/cashflow', name: 'FMSCashFlow', component: () => import('@/views/fms/CashFlow.vue'), meta: { title: '资金流水', domain: 'FMS' } },
      { path: 'ads/campaigns', name: 'ADSCampaigns', component: () => import('@/views/ads/Campaigns.vue'), meta: { title: '广告活动', domain: 'ADS' } },
      { path: 'ads/keywords', name: 'ADSKeywords', component: () => import('@/views/ads/Keywords.vue'), meta: { title: '关键词管理', domain: 'ADS' } },
      { path: 'ads/bidding', name: 'ADSBidding', component: () => import('@/views/ads/Bidding.vue'), meta: { title: '智能竞价', domain: 'ADS' } },
      { path: 'crm/customers', name: 'CRMCustomers', component: () => import('@/views/crm/Customers.vue'), meta: { title: '客户管理', domain: 'CRM' } },
      { path: 'crm/tickets', name: 'CRMTickets', component: () => import('@/views/crm/Tickets.vue'), meta: { title: '工单管理', domain: 'CRM' } },
      { path: 'crm/reviews', name: 'CRMReviews', component: () => import('@/views/crm/Reviews.vue'), meta: { title: '评价管理', domain: 'CRM' } },
      { path: 'fba/shipments', name: 'FBAShipments', component: () => import('@/views/fba/Shipments.vue'), meta: { title: 'FBA货件', domain: 'FBA' } },
      { path: 'fba/inventory', name: 'FBAInventory', component: () => import('@/views/fba/Inventory.vue'), meta: { title: 'FBA库存', domain: 'FBA' } },
      { path: 'fba/fees', name: 'FBAFees', component: () => import('@/views/fba/Fees.vue'), meta: { title: 'FBA费用', domain: 'FBA' } },
      { path: 'bi/metrics', name: 'BIMetrics', component: () => import('@/views/bi/Metrics.vue'), meta: { title: '指标监控', domain: 'BI' } },
      { path: 'bi/reports', name: 'BIReports', component: () => import('@/views/bi/Reports.vue'), meta: { title: '报表中心', domain: 'BI' } },
      { path: 'bi/quality', name: 'BIQuality', component: () => import('@/views/bi/Quality.vue'), meta: { title: '数据质量', domain: 'BI' } },
      { path: 'sys/health', name: 'SYSHealth', component: () => import('@/views/sys/Health.vue'), meta: { title: '系统健康', domain: 'SYS' } },
      { path: 'sys/workflows', name: 'SYSWorkflows', component: () => import('@/views/sys/Workflows.vue'), meta: { title: '工作流', domain: 'SYS' } },
      { path: 'sys/recommendations', name: 'SYSRecommendations', component: () => import('@/views/sys/Recommendations.vue'), meta: { title: '智能推荐', domain: 'SYS' } },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth !== false && !auth.isLoggedIn) {
    return { name: 'Login' }
  }
})

export default router
