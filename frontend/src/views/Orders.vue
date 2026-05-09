<template>
  <div class="page">
    <header class="page-header">
      <h1>订单管理</h1>
      <el-button type="primary" @click="showImport = true">导入订单</el-button>
    </header>

    <el-card>
      <el-table :data="orders" stripe style="width: 100%">
        <el-table-column prop="order_no" label="订单号" width="180" />
        <el-table-column prop="platform" label="平台" width="100" />
        <el-table-column prop="total_amount" label="金额" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="buyer_name" label="买家" />
        <el-table-column prop="order_time" label="下单时间" width="180" />
        <el-table-column label="操作" width="150">
          <el-button size="small" text>查看</el-button>
          <el-button size="small" text type="primary">发货</el-button>
        </el-table-column>
      </el-table>
      <div class="empty-state" v-if="orders.length === 0">暂无订单数据,点击"导入订单"从平台同步</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const orders = ref<any[]>([])
const showImport = ref(false)

function statusType(s: string) {
  const map: Record<string, string> = { pending: 'info', confirmed: 'primary', shipped: 'success', cancelled: 'danger' }
  return map[s] || 'info'
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h1 { margin: 0; font-size: 22px; }
.empty-state { text-align: center; color: #999; padding: 40px; }
</style>
