<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>采购订单</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建采购单</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="po_no" label="采购单号" min-width="160" /><el-table-column prop="supplier_name" label="供应商" min-width="150" /><el-table-column prop="total_amount" label="金额" width="120"><template #default="{ row }">¥{{ row.total_amount }}</template></el-table-column><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'completed' ? 'success' : row.status === 'approved' ? '' : 'warning'" size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="created_at" label="创建时间" width="170" /><el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="approvePO(row)" v-if="row.status === 'draft'">审批</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" title="新建采购单" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="供应商"><el-select v-model="form.supplier_id"><el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" /></el-select></el-form-item>
        <el-form-item label="采购模式"><el-select v-model="form.purchase_mode"><el-option label="普通采购" value="normal" /><el-option label="FBA备货" value="fba" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { scmApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false); const suppliers = ref<any[]>([])
const form = reactive({ supplier_id: '', purchase_mode: 'normal' })

async function loadData() { loading.value = true; try { const res: any = await scmApi.listPurchaseOrders({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function loadSuppliers() { try { const res: any = await scmApi.listSuppliers({}); suppliers.value = res.data?.items || [] } catch {} }
async function approvePO(row: any) { await scmApi.approvePurchaseOrder(row.id); ElMessage.success('审批成功'); loadData() }
async function submitForm() { await scmApi.createPurchaseOrder(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(() => { loadData(); loadSuppliers() })
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
