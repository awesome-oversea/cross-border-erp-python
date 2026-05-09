<template>
  <div class="dashboard-page">
    <el-row :gutter="16" class="kpi-row">
      <el-col :span="6" v-for="kpi in kpiCards" :key="kpi.title">
        <el-card shadow="hover" class="kpi-card">
          <div class="kpi-icon" :style="{ background: kpi.color }">
            <el-icon :size="28"><component :is="kpi.icon" /></el-icon>
          </div>
          <div class="kpi-info">
            <div class="kpi-value">{{ kpi.value }}</div>
            <div class="kpi-title">{{ kpi.title }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header><span>业务概览</span></template>
          <div class="domain-grid">
            <div v-for="d in domains" :key="d.name" class="domain-item" @click="$router.push(d.path)">
              <el-icon :size="32" :color="d.color"><component :is="d.icon" /></el-icon>
              <div class="domain-name">{{ d.name }}</div>
              <div class="domain-desc">{{ d.desc }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header><span>待办事项</span></template>
          <el-empty v-if="!todos.length" description="暂无待办" :image-size="60" />
          <div v-else class="todo-list">
            <div v-for="t in todos" :key="t.id" class="todo-item">
              <el-tag :type="t.priority === 'high' ? 'danger' : t.priority === 'medium' ? 'warning' : 'info'" size="small">{{ t.domain }}</el-tag>
              <span class="todo-title">{{ t.title }}</span>
            </div>
          </div>
        </el-card>
        <el-card shadow="hover" style="margin-top: 16px">
          <template #header><span>系统健康</span></template>
          <div class="health-grid">
            <div v-for="h in healthStatus" :key="h.domain" class="health-item">
              <span class="health-dot" :class="h.status"></span>
              <span>{{ h.domain }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { dashboardApi, sysApi } from '@/api'

const kpiCards = ref([
  { title: '今日订单', value: '0', icon: 'List', color: '#409eff' },
  { title: '待发货', value: '0', icon: 'Van', color: '#e6a23c' },
  { title: '库存预警', value: '0', icon: 'Warning', color: '#f56c6c' },
  { title: '今日营收', value: '¥0', icon: 'Money', color: '#67c23a' },
])

const domains = [
  { name: 'IAM', desc: '组织权限', icon: 'User', color: '#409eff', path: '/iam/users' },
  { name: 'PDM', desc: '产品开发', icon: 'Goods', color: '#67c23a', path: '/pdm/spus' },
  { name: 'SOM', desc: '销售运营', icon: 'Store', color: '#e6a23c', path: '/som/stores' },
  { name: 'OMS', desc: '订单管理', icon: 'List', color: '#f56c6c', path: '/oms/orders' },
  { name: 'SCM', desc: '供应链', icon: 'ShoppingCart', color: '#909399', path: '/scm/purchase-orders' },
  { name: 'WMS', desc: '仓储管理', icon: 'Box', color: '#b37feb', path: '/wms/inventory' },
  { name: 'TMS', desc: '物流管理', icon: 'Van', color: '#36cfc9', path: '/tms/shipments' },
  { name: 'FMS', desc: '财务管理', icon: 'Money', color: '#ffc53d', path: '/fms/settlements' },
  { name: 'ADS', desc: '广告管理', icon: 'Promotion', color: '#ff7a45', path: '/ads/campaigns' },
  { name: 'CRM', desc: '客服售后', icon: 'Service', color: '#597ef7', path: '/crm/customers' },
  { name: 'FBA', desc: 'FBA海外仓', icon: 'Box', color: '#73d13d', path: '/fba/shipments' },
  { name: 'BI', desc: '商业智能', icon: 'DataAnalysis', color: '#9254de', path: '/bi/metrics' },
  { name: 'SYS', desc: '系统设置', icon: 'Setting', color: '#8c8c8c', path: '/sys/health' },
  { name: 'Dashboard', desc: '工作台', icon: 'Monitor', color: '#1890ff', path: '/' },
]

const todos = ref<any[]>([])
const healthStatus = ref<any[]>([])

onMounted(async () => {
  try {
    const res: any = await dashboardApi.getKpiOverview()
    if (res.data) {
      kpiCards.value[0].value = String(res.data.today_orders || 0)
      kpiCards.value[1].value = String(res.data.pending_shipments || 0)
      kpiCards.value[2].value = String(res.data.low_stock_count || 0)
      kpiCards.value[3].value = '¥' + (res.data.today_revenue || 0)
    }
  } catch {}
  try {
    const res: any = await dashboardApi.listTodoItems({ page: 1, page_size: 5 })
    todos.value = res.data?.items || []
  } catch {}
  try {
    const res: any = await sysApi.checkSystemHealth()
    if (res.data?.domains) {
      healthStatus.value = Object.entries(res.data.domains).map(([domain, info]: [string, any]) => ({
        domain, status: info.status || 'unknown',
      }))
    }
  } catch {}
})
</script>

<style scoped>
.dashboard-page { padding: 4px; }
.kpi-card { display: flex; align-items: center; }
.kpi-card :deep(.el-card__body) { display: flex; align-items: center; gap: 16px; width: 100%; }
.kpi-icon { width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.kpi-value { font-size: 24px; font-weight: 700; color: #303133; }
.kpi-title { font-size: 13px; color: #909399; margin-top: 4px; }
.domain-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.domain-item { text-align: center; padding: 16px 8px; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
.domain-item:hover { background: #f5f7fa; transform: translateY(-2px); }
.domain-name { font-size: 14px; font-weight: 600; margin-top: 8px; }
.domain-desc { font-size: 12px; color: #909399; margin-top: 4px; }
.todo-list { max-height: 240px; overflow: auto; }
.todo-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.todo-title { font-size: 13px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.health-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.health-item { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.health-dot { width: 8px; height: 8px; border-radius: 50%; }
.health-dot.healthy { background: #67c23a; }
.health-dot.degraded { background: #e6a23c; }
.health-dot.unhealthy { background: #f56c6c; }
.health-dot.unknown { background: #909399; }
</style>
