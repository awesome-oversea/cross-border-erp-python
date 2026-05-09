<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><el-button @click="$router.back()"><el-icon><ArrowLeft /></el-icon>返回</el-button><h3>订单详情</h3></div>
      <el-descriptions :column="3" border v-loading="loading">
        <el-descriptions-item label="订单号">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item label="平台">{{ order.platform }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="order.status === 'delivered' ? 'success' : 'info'" size="small">{{ order.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="买家">{{ order.buyer_name }}</el-descriptions-item>
        <el-descriptions-item label="金额">¥{{ order.total_amount }}</el-descriptions-item>
        <el-descriptions-item label="下单时间">{{ order.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { omsApi } from '@/api'

const route = useRoute()
const loading = ref(false)
const order = ref<any>({})

onMounted(async () => {
  loading.value = true
  try { const res: any = await omsApi.getOrder(route.params.id as string); order.value = res.data || {} } finally { loading.value = false }
})
</script>

<style scoped>.page-container { padding: 4px; }.page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }.page-header h3 { margin: 0; }</style>
