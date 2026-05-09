<template>
  <div class="page-container">
    <el-row :gutter="16">
      <el-col :span="8"><el-card shadow="hover"><el-statistic title="总营收" :value="profitData.total_revenue || 0" prefix="¥" /></el-card></el-col>
      <el-col :span="8"><el-card shadow="hover"><el-statistic title="总成本" :value="profitData.total_cost || 0" prefix="¥" /></el-card></el-col>
      <el-col :span="8"><el-card shadow="hover"><el-statistic title="净利润" :value="profitData.net_profit || 0" prefix="¥" /><template #footer><span>利润率: {{ profitData.profit_margin || 0 }}%</span></template></el-card></el-col>
    </el-row>
    <el-card shadow="never" style="margin-top:16px">
      <template #header><span>利润趋势</span></template>
      <v-chart :option="chartOption" style="height: 400px" autoresize />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { fmsApi } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const profitData = reactive({ total_revenue: 0, total_cost: 0, net_profit: 0, profit_margin: 0 })
const chartOption = ref({})

onMounted(async () => {
  try { const res: any = await fmsApi.getProfitAnalysis({}); Object.assign(profitData, res.data || {}) } catch {}
  chartOption.value = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['营收', '成本', '利润'] },
    xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
    yAxis: { type: 'value' },
    series: [
      { name: '营收', type: 'line', data: [120, 132, 101, 134, 90, 230] },
      { name: '成本', type: 'line', data: [80, 92, 71, 94, 60, 150] },
      { name: '利润', type: 'line', data: [40, 40, 30, 40, 30, 80] },
    ],
  }
})
</script>

<style scoped>.page-container{padding:4px}</style>
