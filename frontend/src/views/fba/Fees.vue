<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="8"><el-card shadow="hover"><el-statistic title="月仓储费" :value="feeData.storage_fee || 0" prefix="¥" /></el-card></el-col>
      <el-col :span="8"><el-card shadow="hover"><el-statistic title="月配送费" :value="feeData.fulfillment_fee || 0" prefix="¥" /></el-card></el-col>
      <el-col :span="8"><el-card shadow="hover"><el-statistic title="月长期仓储费" :value="feeData.long_term_fee || 0" prefix="¥" /></el-card></el-col>
    </el-row>
    <el-card shadow="never" style="margin-top:16px"><div class="page-header"><h3>FBA费用明细</h3></div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="sku" label="SKU" min-width="140" /><el-table-column prop="fee_type" label="费用类型" width="120" /><el-table-column prop="amount" label="金额" width="120"><template #default="{ row }">¥{{ row.amount }}</template></el-table-column><el-table-column prop="quantity" label="数量" width="80" /><el-table-column prop="period" label="期间" width="120" /><el-table-column prop="description" label="描述" min-width="200" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { fbaApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([])
const feeData = reactive({ storage_fee: 0, fulfillment_fee: 0, long_term_fee: 0 })

async function loadData() {
  loading.value = true
  try {
    const res: any = await fbaApi.listFees({}); tableData.value = res.data?.items || []
    if (res.data?.summary) Object.assign(feeData, res.data.summary)
  } finally { loading.value = false }
}
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
