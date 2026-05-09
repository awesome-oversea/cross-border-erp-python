<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>物流追踪</h3>
    <div class="search-bar"><el-input v-model="trackingNo" placeholder="输入物流单号/追踪号" clearable style="width:300px" @keyup.enter="trackShipment" /><el-button type="primary" @click="trackShipment">查询</el-button></div></div>
    <el-empty v-if="!trackingResult && !loading" description="请输入物流单号查询" />
    <el-timeline v-else-if="trackingResult" style="margin-top: 20px; padding: 0 20px">
      <el-timeline-item v-for="(event, idx) in trackingResult.events" :key="idx" :timestamp="event.time" :type="idx === 0 ? 'primary' : 'info'" placement="top">
        {{ event.description }}
      </el-timeline-item>
    </el-timeline>
  </el-card></div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { tmsApi } from '@/api'

const trackingNo = ref('')
const trackingResult = ref<any>(null)
const loading = ref(false)

async function trackShipment() {
  if (!trackingNo.value) return
  loading.value = true
  try { const res: any = await tmsApi.trackShipment(trackingNo.value); trackingResult.value = res.data || null } finally { loading.value = false }
}
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}.search-bar{display:flex;gap:8px}</style>
