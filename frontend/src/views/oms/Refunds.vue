<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>退款管理</h3></div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="refund_no" label="退款单号" min-width="160" />
        <el-table-column prop="order_no" label="原订单号" min-width="160" />
        <el-table-column prop="refund_amount" label="退款金额" width="120"><template #default="{ row }">¥{{ row.refund_amount }}</template></el-table-column>
        <el-table-column prop="reason" label="退款原因" min-width="200" />
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'completed' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="created_at" label="申请时间" width="170" />
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top: 16px; justify-content: flex-end" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { omsApi } from '@/api'

const loading = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

async function loadData() { loading.value = true; try { const res: any = await omsApi.listRefundOrders({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container { padding: 4px; }.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }.page-header h3 { margin: 0; }</style>
