<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>资金流水</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="transaction_no" label="流水号" min-width="160" /><el-table-column prop="type" label="类型" width="120" /><el-table-column prop="amount" label="金额" width="120"><template #default="{ row }"><span :style="{ color: row.direction === 'in' ? '#67c23a' : '#f56c6c' }">{{ row.direction === 'in' ? '+' : '-' }}¥{{ row.amount }}</span></template></el-table-column><el-table-column prop="balance_after" label="余额" width="120"><template #default="{ row }">¥{{ row.balance_after }}</template></el-table-column><el-table-column prop="description" label="描述" min-width="200" /><el-table-column prop="created_at" label="时间" width="170" />
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fmsApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
async function loadData() { loading.value = true; try { const res: any = await fmsApi.listCashFlow({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
