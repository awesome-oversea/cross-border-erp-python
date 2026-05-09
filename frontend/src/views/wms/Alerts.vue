<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>库存预警</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="sku_code" label="SKU编码" min-width="140" /><el-table-column prop="sku_name" label="SKU名称" min-width="180" /><el-table-column prop="warehouse_name" label="仓库" width="120" /><el-table-column prop="qty_available" label="可用数量" width="100" /><el-table-column prop="reorder_point" label="补货点" width="100" /><el-table-column prop="alert_type" label="预警类型" width="120"><template #default="{ row }"><el-tag type="danger" size="small">{{ row.alert_type || '低库存' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="100" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="createReplenishment(row)">补货</el-button></template></el-table-column>
    </el-table></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { wmsApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([])
async function loadData() { loading.value = true; try { const res: any = await wmsApi.listAlerts({}); tableData.value = res.data?.items || res.data || [] } finally { loading.value = false } }
function createReplenishment(row: any) { ElMessage.info(`创建补货计划: ${row.sku_code}`) }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
