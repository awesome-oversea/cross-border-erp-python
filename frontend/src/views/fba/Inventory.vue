<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>FBA库存</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="sku" label="SKU" min-width="140" /><el-table-column prop="fnsku" label="FNSKU" width="140" /><el-table-column prop="asin" label="ASIN" width="140" /><el-table-column prop="fulfillable" label="可售" width="80" /><el-table-column prop="reserved" label="预留" width="80" /><el-table-column prop="inbound" label="在途" width="80" /><el-table-column prop="warehouse" label="仓库" width="120" /><el-table-column prop="age_days" label="库龄(天)" width="100" />
    </el-table></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fbaApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([])
async function loadData() { loading.value = true; try { const res: any = await fbaApi.listInventory({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
