<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>评价管理</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="product_name" label="产品" min-width="180" /><el-table-column prop="reviewer" label="评价人" width="120" /><el-table-column prop="rating" label="评分" width="160"><template #default="{ row }"><el-rate v-model="row.rating" disabled size="small" /></template></el-table-column><el-table-column prop="content" label="评价内容" min-width="250" show-overflow-tooltip /><el-table-column prop="sentiment" label="情感" width="100"><template #default="{ row }"><el-tag :type="row.sentiment === 'positive' ? 'success' : row.sentiment === 'negative' ? 'danger' : 'warning'" size="small">{{ row.sentiment }}</el-tag></template></el-table-column><el-table-column prop="replied" label="已回复" width="80"><template #default="{ row }"><el-icon :color="row.replied ? '#67c23a' : '#909399'"><Select v-if="row.replied" /><CloseBold v-else /></el-icon></template></el-table-column>
    </el-table></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { crmApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([])
async function loadData() { loading.value = true; try { const res: any = await crmApi.listReviews({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
