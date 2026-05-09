<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>数据质量</h3></div>
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="总检查项" :value="qualityData.total_checks || 0" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="通过率" :value="qualityData.pass_rate || 0" suffix="%" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="异常数" :value="qualityData.anomalies || 0" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="修复率" :value="qualityData.fix_rate || 0" suffix="%" /></el-card></el-col>
    </el-row>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="table_name" label="数据表" min-width="160" /><el-table-column prop="check_type" label="检查类型" width="120" /><el-table-column prop="result" label="结果" width="100"><template #default="{ row }"><el-tag :type="row.result === 'pass' ? 'success' : 'danger'" size="small">{{ row.result }}</el-tag></template></el-table-column><el-table-column prop="issue_count" label="问题数" width="80" /><el-table-column prop="details" label="详情" min-width="250" show-overflow-tooltip /><el-table-column prop="checked_at" label="检查时间" width="170" />
    </el-table></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { biApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([])
const qualityData = reactive({ total_checks: 0, pass_rate: 0, anomalies: 0, fix_rate: 0 })

async function loadData() {
  loading.value = true
  try {
    const res: any = await biApi.listQualityChecks({}); tableData.value = res.data?.items || []
    if (res.data?.summary) Object.assign(qualityData, res.data.summary)
  } finally { loading.value = false }
}
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
