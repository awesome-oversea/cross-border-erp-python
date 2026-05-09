<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>供应商管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增供应商</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="name" label="供应商名称" min-width="180" /><el-table-column prop="code" label="编码" width="120" /><el-table-column prop="contact_name" label="联系人" width="120" /><el-table-column prop="contact_phone" label="联系电话" width="140" /><el-table-column prop="rating" label="评级" width="100"><template #default="{ row }"><el-rate v-model="row.rating" disabled size="small" /></template></el-table-column><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="editRow(row)">编辑</el-button><el-button link type="danger" size="small" @click="deleteRow(row)">删除</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" :title="editingId ? '编辑供应商' : '新增供应商'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="编码"><el-input v-model="form.code" /></el-form-item><el-form-item label="联系人"><el-input v-model="form.contact_name" /></el-form-item><el-form-item label="联系电话"><el-input v-model="form.contact_phone" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { scmApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false); const editingId = ref('')
const form = reactive({ name: '', code: '', contact_name: '', contact_phone: '' })

async function loadData() { loading.value = true; try { const res: any = await scmApi.listSuppliers({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
function editRow(row: any) { editingId.value = row.id; Object.assign(form, row); showDialog.value = true }
async function deleteRow(row: any) { await ElMessageBox.confirm(`确定删除供应商 ${row.name}?`, '提示', { type: 'warning' }); await scmApi.deleteSupplier(row.id); ElMessage.success('删除成功'); loadData() }
async function submitForm() { if (editingId.value) { await scmApi.updateSupplier(editingId.value, form) } else { await scmApi.createSupplier(form) }; ElMessage.success('操作成功'); showDialog.value = false; editingId.value = ''; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
