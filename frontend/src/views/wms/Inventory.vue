<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>库存管理</h3>
        <div class="search-bar"><el-input v-model="search.keyword" placeholder="SKU编码/名称" clearable style="width:200px" @keyup.enter="loadData" /><el-select v-model="search.warehouse_id" placeholder="仓库" clearable style="width:140px"><el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" /></el-select><el-button type="primary" @click="loadData">搜索</el-button></div>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="sku_code" label="SKU编码" min-width="140" />
        <el-table-column prop="sku_name" label="SKU名称" min-width="180" />
        <el-table-column prop="warehouse_name" label="仓库" width="120" />
        <el-table-column prop="qty_on_hand" label="在库数量" width="100" />
        <el-table-column prop="qty_available" label="可用数量" width="100" />
        <el-table-column prop="qty_reserved" label="预留数量" width="100" />
        <el-table-column prop="reorder_point" label="补货点" width="100" />
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.qty_available <= row.reorder_point ? 'danger' : 'success'" size="small">{{ row.qty_available <= row.reorder_point ? '低库存' : '正常' }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="100" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="adjustStock(row)">调整</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { wmsApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref<any[]>([])
const warehouses = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const search = reactive({ keyword: '', warehouse_id: '' })

async function loadData() { loading.value = true; try { const res: any = await wmsApi.listInventory({ page: page.value, page_size: pageSize.value, ...search }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function loadWarehouses() { try { const res: any = await wmsApi.listWarehouses({}); warehouses.value = res.data?.items || [] } catch {} }
function adjustStock(row: any) { ElMessage.info(`调整库存: ${row.sku_code}`) }

onMounted(() => { loadData(); loadWarehouses() })
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}.search-bar{display:flex;gap:8px}</style>
