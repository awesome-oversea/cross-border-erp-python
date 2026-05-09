<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>运费管理</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="carrier" label="承运商" width="120" /><el-table-column prop="channel" label="渠道" width="120" /><el-table-column prop="zone" label="区域" width="100" /><el-table-column prop="weight_range" label="重量段" width="140" /><el-table-column prop="base_rate" label="基础费" width="100"><template #default="{ row }">¥{{ row.base_rate }}</template></el-table-column><el-table-column prop="per_kg_rate" label="续重费/kg" width="120"><template #default="{ row }">¥{{ row.per_kg_rate }}</template></el-table-column><el-table-column prop="effective_date" label="生效日期" width="120" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
    </el-table></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tmsApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([])
async function loadData() { loading.value = true; try { const res: any = await tmsApi.listFreightRates({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
