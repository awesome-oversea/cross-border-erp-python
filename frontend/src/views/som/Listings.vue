<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>Listing管理</h3>
    <div class="search-bar"><el-input v-model="search.keyword" placeholder="标题/SKU" clearable style="width:200px" @keyup.enter="loadData" /><el-select v-model="search.status" placeholder="状态" clearable style="width:120px"><el-option label="Active" value="active" /><el-option label="Inactive" value="inactive" /><el-option label="Draft" value="draft" /></el-select><el-button type="primary" @click="loadData">搜索</el-button></div></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="title" label="标题" min-width="250" show-overflow-tooltip /><el-table-column prop="sku" label="SKU" width="120" /><el-table-column prop="platform" label="平台" width="100" /><el-table-column prop="price" label="价格" width="100"><template #default="{ row }">{{ row.currency || '$' }}{{ row.price }}</template></el-table-column><el-table-column prop="stock" label="库存" width="80" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="syncListing(row)">同步</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { somApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const search = reactive({ keyword: '', status: '' })

async function loadData() { loading.value = true; try { const res: any = await somApi.listListings({ page: page.value, page_size: pageSize.value, ...search }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function syncListing(row: any) { await somApi.syncListing(row.id); ElMessage.success('同步已触发') }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}.search-bar{display:flex;gap:8px}</style>
