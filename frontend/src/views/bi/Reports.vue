<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>报表中心</h3></div>
      <el-row :gutter="16">
        <el-col :span="8" v-for="report in reports" :key="report.id">
          <el-card shadow="hover" class="report-card" @click="viewReport(report)">
            <el-icon :size="40" :color="report.color"><component :is="report.icon" /></el-icon>
            <div class="report-name">{{ report.name }}</div>
            <div class="report-desc">{{ report.description }}</div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
    <el-card shadow="never" style="margin-top:16px">
      <div class="page-header"><h3>已生成报表</h3></div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="report_name" label="报表名称" min-width="200" />
        <el-table-column prop="report_type" label="类型" width="120" />
        <el-table-column prop="period" label="期间" width="120" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag :type="row.status === 'completed' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="created_at" label="生成时间" width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }"><el-button link type="primary" size="small" @click="downloadReport(row)">下载</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { biApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([])
const reports = [
  { id: 'sales', name: '销售报表', description: '多维度销售数据分析', icon: 'TrendCharts', color: '#409eff' },
  { id: 'inventory', name: '库存报表', description: '库存周转与预警分析', icon: 'Box', color: '#67c23a' },
  { id: 'finance', name: '财务报表', description: '收支利润与结算分析', icon: 'Money', color: '#e6a23c' },
  { id: 'ads', name: '广告报表', description: '广告效果与ROI分析', icon: 'Promotion', color: '#f56c6c' },
  { id: 'customer', name: '客户报表', description: '客户画像与RFM分析', icon: 'User', color: '#909399' },
  { id: 'logistics', name: '物流报表', description: '物流时效与成本分析', icon: 'Van', color: '#b37feb' },
]

async function loadData() { loading.value = true; try { const res: any = await biApi.listReports({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
function viewReport(report: any) { ElMessage.info(`查看报表: ${report.name}`) }
function downloadReport(row: any) { ElMessage.info(`下载报表: ${row.report_name}`) }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}.report-card{text-align:center;padding:24px;cursor:pointer;transition:all 0.2s}.report-card:hover{transform:translateY(-4px);box-shadow:0 4px 12px rgba(0,0,0,0.1)}.report-name{font-size:16px;font-weight:600;margin-top:12px}.report-desc{font-size:12px;color:#909399;margin-top:4px}</style>
