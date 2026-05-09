<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>合规检查</h3><el-button type="primary" @click="runCheck"><el-icon><CircleCheck /></el-icon>执行合规检查</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="product_name" label="产品" min-width="180" /><el-table-column prop="check_type" label="检查类型" width="120" /><el-table-column prop="marketplace" label="目标市场" width="120" /><el-table-column prop="result" label="结果" width="100"><template #default="{ row }"><el-tag :type="row.result === 'pass' ? 'success' : row.result === 'fail' ? 'danger' : 'warning'" size="small">{{ row.result }}</el-tag></template></el-table-column><el-table-column prop="issues" label="问题" min-width="250" show-overflow-tooltip /><el-table-column prop="checked_at" label="检查时间" width="170" />
    </el-table></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { pdmApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([])
async function loadData() { loading.value = true; try { const res: any = await pdmApi.listComplianceChecks({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
async function runCheck() { try { await pdmApi.runComplianceCheck({}); ElMessage.success('合规检查已触发'); loadData() } catch { ElMessage.error('检查失败') } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
