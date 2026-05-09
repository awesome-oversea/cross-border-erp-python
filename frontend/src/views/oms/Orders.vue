<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>订单管理</h3>
        <div class="search-bar">
          <el-input v-model="search.keyword" placeholder="订单号/买家" clearable style="width: 200px" @keyup.enter="loadData" />
          <el-select v-model="search.status" placeholder="状态" clearable style="width: 120px">
            <el-option v-for="s in statuses" :key="s" :label="s" :value="s" />
          </el-select>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </div>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="order_no" label="订单号" min-width="160" />
        <el-table-column prop="platform" label="平台" width="100" />
        <el-table-column prop="store_name" label="店铺" width="120" />
        <el-table-column prop="buyer_name" label="买家" width="120" />
        <el-table-column prop="total_amount" label="金额" width="100"><template #default="{ row }">¥{{ row.total_amount }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="$router.push(`/oms/orders/${row.id}`)">详情</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top: 16px; justify-content: flex-end" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { omsApi } from '@/api'

const loading = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const statuses = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']
const search = reactive({ keyword: '', status: '' })

function statusType(s: string) { return s === 'delivered' ? 'success' : s === 'cancelled' ? 'danger' : s === 'shipped' ? 'warning' : 'info' }

async function loadData() {
  loading.value = true
  try { const res: any = await omsApi.listOrders({ page: page.value, page_size: pageSize.value, ...search }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false }
}
onMounted(loadData)
</script>

<style scoped>.page-container { padding: 4px; }.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }.page-header h3 { margin: 0; }.search-bar { display: flex; gap: 8px; }</style>
