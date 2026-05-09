<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>出库管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建出库单</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe><el-table-column prop="outbound_no" label="出库单号" min-width="160" /><el-table-column prop="warehouse_name" label="仓库" width="120" /><el-table-column prop="outbound_type" label="出库类型" width="120" /><el-table-column prop="total_qty" label="总数量" width="100" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="created_at" label="创建时间" width="170" /></el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { wmsApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0); const showDialog = ref(false)
async function loadData() { loading.value = true; try { const res: any = await wmsApi.listOutboundOrders({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
