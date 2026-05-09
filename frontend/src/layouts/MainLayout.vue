<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <el-icon :size="28"><Shop /></el-icon>
        <span v-show="!isCollapse" class="logo-text">跨境电商ERP</span>
      </div>
      <el-scrollbar>
        <el-menu :default-active="route.path" :collapse="isCollapse" router class="sidebar-menu">
          <el-menu-item index="/">
            <el-icon><Monitor /></el-icon>
            <template #title>工作台</template>
          </el-menu-item>
          <el-sub-menu index="iam">
            <template #title><el-icon><User /></el-icon><span>IAM权限</span></template>
            <el-menu-item index="/iam/users">用户管理</el-menu-item>
            <el-menu-item index="/iam/roles">角色权限</el-menu-item>
            <el-menu-item index="/iam/orgs">组织管理</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="pdm">
            <template #title><el-icon><Goods /></el-icon><span>PDM产品</span></template>
            <el-menu-item index="/pdm/spus">SPU管理</el-menu-item>
            <el-menu-item index="/pdm/skus">SKU管理</el-menu-item>
            <el-menu-item index="/pdm/compliance">合规检查</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="som">
            <template #title><el-icon><Store /></el-icon><span>SOM运营</span></template>
            <el-menu-item index="/som/stores">店铺管理</el-menu-item>
            <el-menu-item index="/som/listings">Listing管理</el-menu-item>
            <el-menu-item index="/som/pricing">自动定价</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="oms">
            <template #title><el-icon><List /></el-icon><span>OMS订单</span></template>
            <el-menu-item index="/oms/orders">订单管理</el-menu-item>
            <el-menu-item index="/oms/refunds">退款管理</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="scm">
            <template #title><el-icon><ShoppingCart /></el-icon><span>SCM供应链</span></template>
            <el-menu-item index="/scm/purchase-orders">采购订单</el-menu-item>
            <el-menu-item index="/scm/suppliers">供应商管理</el-menu-item>
            <el-menu-item index="/scm/inquiries">询价管理</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="wms">
            <template #title><el-icon><Box /></el-icon><span>WMS仓储</span></template>
            <el-menu-item index="/wms/inventory">库存管理</el-menu-item>
            <el-menu-item index="/wms/inbound">入库管理</el-menu-item>
            <el-menu-item index="/wms/outbound">出库管理</el-menu-item>
            <el-menu-item index="/wms/alerts">库存预警</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="tms">
            <template #title><el-icon><Van /></el-icon><span>TMS物流</span></template>
            <el-menu-item index="/tms/shipments">物流管理</el-menu-item>
            <el-menu-item index="/tms/tracking">物流追踪</el-menu-item>
            <el-menu-item index="/tms/freight">运费管理</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="fms">
            <template #title><el-icon><Money /></el-icon><span>FMS财务</span></template>
            <el-menu-item index="/fms/settlements">结算管理</el-menu-item>
            <el-menu-item index="/fms/profit">利润分析</el-menu-item>
            <el-menu-item index="/fms/cashflow">资金流水</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="ads">
            <template #title><el-icon><Promotion /></el-icon><span>ADS广告</span></template>
            <el-menu-item index="/ads/campaigns">广告活动</el-menu-item>
            <el-menu-item index="/ads/keywords">关键词管理</el-menu-item>
            <el-menu-item index="/ads/bidding">智能竞价</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="crm">
            <template #title><el-icon><Service /></el-icon><span>CRM客服</span></template>
            <el-menu-item index="/crm/customers">客户管理</el-menu-item>
            <el-menu-item index="/crm/tickets">工单管理</el-menu-item>
            <el-menu-item index="/crm/reviews">评价管理</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="fba">
            <template #title><el-icon><Box /></el-icon><span>FBA海外仓</span></template>
            <el-menu-item index="/fba/shipments">FBA货件</el-menu-item>
            <el-menu-item index="/fba/inventory">FBA库存</el-menu-item>
            <el-menu-item index="/fba/fees">FBA费用</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="bi">
            <template #title><el-icon><DataAnalysis /></el-icon><span>BI智能</span></template>
            <el-menu-item index="/bi/metrics">指标监控</el-menu-item>
            <el-menu-item index="/bi/reports">报表中心</el-menu-item>
            <el-menu-item index="/bi/quality">数据质量</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="sys">
            <template #title><el-icon><Setting /></el-icon><span>SYS系统</span></template>
            <el-menu-item index="/sys/health">系统健康</el-menu-item>
            <el-menu-item index="/sys/workflows">工作流</el-menu-item>
            <el-menu-item index="/sys/recommendations">智能推荐</el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>
    </el-aside>
    <el-container>
      <el-header class="top-header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse">
            <Fold v-if="!isCollapse" /><Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.domain">{{ route.meta.domain }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag type="info" size="small">租户: {{ auth.tenantId || '-' }}</el-tag>
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon><UserFilled /></el-icon>
              {{ auth.username || '未登录' }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isCollapse = ref(false)

function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.main-layout { height: 100vh; }
.sidebar { background: #001529; overflow: hidden; }
.logo { height: 60px; display: flex; align-items: center; justify-content: center; color: #fff; gap: 8px; }
.logo-text { font-size: 16px; font-weight: 600; white-space: nowrap; }
.sidebar-menu { border-right: none; }
.sidebar-menu:not(.el-menu--collapse) { width: 220px; }
.top-header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e8e8e8; background: #fff; }
.header-left { display: flex; align-items: center; gap: 16px; }
.collapse-btn { cursor: pointer; font-size: 20px; }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-info { display: flex; align-items: center; gap: 4px; cursor: pointer; }
.main-content { background: #f0f2f5; min-height: 0; overflow: auto; }
</style>
