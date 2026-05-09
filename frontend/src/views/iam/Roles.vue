<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>角色权限</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增角色</el-button></div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="name" label="角色名称" min-width="150" />
        <el-table-column prop="code" label="角色编码" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="editRow(row)">编辑</el-button><el-button link type="danger" size="small" @click="deleteRow(row)">删除</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top: 16px; justify-content: flex-end" />
    </el-card>
    <el-dialog v-model="showDialog" :title="editingId ? '编辑角色' : '新增角色'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="角色名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="角色编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { iamApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const tableData = ref<any[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showDialog = ref(false)
const editingId = ref('')
const form = reactive({ name: '', code: '', description: '' })

async function loadData() {
  loading.value = true
  try { const res: any = await iamApi.listRoles({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false }
}
function editRow(row: any) { editingId.value = row.id; Object.assign(form, row); showDialog.value = true }
async function deleteRow(row: any) { await ElMessageBox.confirm(`确定删除角色 ${row.name}?`, '提示', { type: 'warning' }); await iamApi.deleteRole(row.id); ElMessage.success('删除成功'); loadData() }
async function submitForm() { if (editingId.value) { await iamApi.updateRole(editingId.value, form) } else { await iamApi.createRole(form) }; ElMessage.success(editingId.value ? '更新成功' : '创建成功'); showDialog.value = false; editingId.value = ''; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container { padding: 4px; }.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }.page-header h3 { margin: 0; }</style>
