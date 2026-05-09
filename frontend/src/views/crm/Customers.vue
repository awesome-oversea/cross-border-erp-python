<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>客户管理</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="customer_name" label="客户名称" min-width="150" /><el-table-column prop="email" label="邮箱" min-width="180" /><el-table-column prop="platform" label="平台" width="100" /><el-table-column prop="total_orders" label="订单数" width="100" /><el-table-column prop="total_spent" label="消费总额" width="120"><template #default="{ row }">¥{{ row.total_spent }}</template></el-table-column><el-table-column prop="rfm_segment" label="RFM分层" width="120"><template #default="{ row }"><el-tag size="small">{{ row.rfm_segment || '-' }}</el-tag></template></el-table-column><el-table-column prop="last_order_at" label="最近下单" width="170" />
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { crmApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
async function loadData() { loading.value = true; try { const res: any = await crmApi.listCustomers({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
