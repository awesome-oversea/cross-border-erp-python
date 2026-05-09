<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>关键词管理</h3></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="keyword_text" label="关键词" min-width="160" /><el-table-column prop="match_type" label="匹配类型" width="100" /><el-table-column prop="bid" label="竞价" width="100"><template #default="{ row }">¥{{ row.bid }}</template></el-table-column><el-table-column prop="impressions" label="曝光" width="100" /><el-table-column prop="clicks" label="点击" width="100" /><el-table-column prop="ctr" label="CTR" width="100"><template #default="{ row }">{{ row.ctr }}%</template></el-table-column><el-table-column prop="conversions" label="转化" width="100" /><el-table-column prop="campaign_name" label="所属活动" min-width="160" />
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adsApi } from '@/api'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
async function loadData() { loading.value = true; try { const res: any = await adsApi.listKeywords({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
