<template>
  <div class="page-container">
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="系统状态" :value="health.overall || '-'" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="在线服务" :value="health.healthy_count || 0" suffix="个" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="异常服务" :value="health.unhealthy_count || 0" suffix="个" /></el-card></el-col>
      <el-col :span="6"><el-card shadow="hover"><el-statistic title="检查时间" :value="health.checked_at || '-'" /></el-card></el-col>
    </el-row>
    <el-card shadow="never"><div class="page-header"><h3>服务健康状态</h3><el-button type="primary" @click="loadData"><el-icon><Refresh /></el-icon>刷新</el-button></div>
      <el-table :data="domainHealth" v-loading="loading" stripe>
        <el-table-column prop="domain" label="域" width="120" /><el-table-column prop="status" label="状态" width="120"><template #default="{ row }"><el-tag :type="row.status === 'healthy' ? 'success' : row.status === 'degraded' ? 'warning' : 'danger'" size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="response_time" label="响应时间" width="120"><template #default="{ row }">{{ row.response_time }}ms</template></el-table-column><el-table-column prop="uptime" label="可用率" width="100"><template #default="{ row }">{{ row.uptime }}%</template></el-table-column><el-table-column prop="last_error" label="最近错误" min-width="250" show-overflow-tooltip /><el-table-column prop="last_check" label="最后检查" width="170" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { sysApi } from '@/api'

const loading = ref(false); const domainHealth = ref<any[]>([])
const health = reactive({ overall: '-', healthy_count: 0, unhealthy_count: 0, checked_at: '-' })

async function loadData() {
  loading.value = true
  try {
    const res: any = await sysApi.checkSystemHealth()
    if (res.data) {
      health.overall = res.data.overall_status || '-'
      health.checked_at = res.data.checked_at || '-'
      if (res.data.domains) {
        domainHealth.value = Object.entries(res.data.domains).map(([domain, info]: [string, any]) => ({
          domain, status: info.status || 'unknown', response_time: info.response_time || 0, uptime: info.uptime || 0, last_error: info.last_error || '', last_check: info.last_check || '',
        }))
        health.healthy_count = domainHealth.value.filter(d => d.status === 'healthy').length
        health.unhealthy_count = domainHealth.value.filter(d => d.status !== 'healthy').length
      }
    }
  } finally { loading.value = false }
}
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
