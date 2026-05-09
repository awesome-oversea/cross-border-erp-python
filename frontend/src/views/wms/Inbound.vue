<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>入库管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建入库单</el-button></div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="inbound_no" label="入库单号" min-width="160" />
        <el-table-column prop="warehouse_name" label="仓库" width="120" />
        <el-table-column prop="inbound_type" label="入库类型" width="120" />
        <el-table-column prop="total_qty" label="总数量" width="100" />
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'completed' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" />
    </el-card>
    <el-dialog v-model="showDialog" title="新建入库单" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="仓库"><el-select v-model="form.warehouse_id"><el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" /></el-select></el-form-item>
        <el-form-item label="入库类型"><el-select v-model="form.inbound_type"><el-option label="采购入库" value="purchase" /><el-option label="退货入库" value="return" /><el-option label="调拨入库" value="transfer" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { wmsApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false); const warehouses = ref<any[]>([])
const form = reactive({ warehouse_id: '', inbound_type: 'purchase' })

async function loadData() { loading.value = true; try { const res: any = await wmsApi.listInboundOrders({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function loadWarehouses() { try { const res: any = await wmsApi.listWarehouses({}); warehouses.value = res.data?.items || [] } catch {} }
async function submitForm() { await wmsApi.createInboundOrder(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(() => { loadData(); loadWarehouses() })
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
