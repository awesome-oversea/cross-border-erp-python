<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="6" v-for="m in metricCards" :key="m.title">
        <el-card shadow="hover" class="metric-card">
          <el-statistic :title="m.title" :value="m.value" :suffix="m.suffix" />
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="never" style="margin-top:16px">
      <template #header><span>指标趋势</span></template>
      <v-chart :option="chartOption" style="height: 400px" autoresize />
    </el-card>
    <el-card shadow="never" style="margin-top:16px"><div class="page-header"><h3>指标列表</h3></div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="metric_name" label="指标名称" min-width="180" /><el-table-column prop="metric_code" label="指标编码" width="140" /><el-table-column prop="value" label="当前值" width="120" /><el-table-column prop="unit" label="单位" width="80" /><el-table-column prop="trend" label="趋势" width="100"><template #default="{ row }"><el-tag :type="row.trend === 'up' ? 'success' : row.trend === 'down' ? 'danger' : 'info'" size="small">{{ row.trend === 'up' ? '↑' : row.trend === 'down' ? '↓' : '→' }}</el-tag></template></el-table-column><el-table-column prop="updated_at" label="更新时间" width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { biApi } from '@/api'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

const loading = ref(false); const tableData = ref<any[]>([])
const metricCards = ref([
  { title: 'GMV', value: 0, suffix: '¥' },
  { title: '订单量', value: 0, suffix: '单' },
  { title: '客单价', value: 0, suffix: '¥' },
  { title: '转化率', value: 0, suffix: '%' },
])
const chartOption = ref({})

onMounted(async () => {
  try { const res: any = await biApi.listMetrics({}); tableData.value = res.data?.items || [] } catch {}
  chartOption.value = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['GMV', '订单量'] },
    xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
    yAxis: [{ type: 'value', name: 'GMV' }, { type: 'value', name: '订单量' }],
    series: [
      { name: 'GMV', type: 'bar', data: [12000, 15000, 11000, 18000, 14000, 22000] },
      { name: '订单量', type: 'line', yAxisIndex: 1, data: [120, 150, 110, 180, 140, 220] },
    ],
  }
})
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
