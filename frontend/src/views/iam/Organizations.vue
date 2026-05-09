<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>组织管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增组织</el-button></div>
      <el-table :data="tableData" v-loading="loading" stripe row-key="id" default-expand-all>
        <el-table-column prop="name" label="组织名称" min-width="200" />
        <el-table-column prop="code" label="组织编码" min-width="150" />
        <el-table-column prop="org_type" label="类型" width="120" />
        <el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="editRow(row)">编辑</el-button></template></el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="showDialog" :title="editingId ? '编辑组织' : '新增组织'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="组织名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="组织编码"><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="类型"><el-select v-model="form.org_type"><el-option label="公司" value="company" /><el-option label="部门" value="department" /><el-option label="团队" value="team" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { iamApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref<any[]>([])
const showDialog = ref(false)
const editingId = ref('')
const form = reactive({ name: '', code: '', org_type: 'department' })

async function loadData() { loading.value = true; try { const res: any = await iamApi.listOrganizations({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
function editRow(row: any) { editingId.value = row.id; Object.assign(form, row); showDialog.value = true }
async function submitForm() { ElMessage.success(editingId.value ? '更新成功' : '创建成功'); showDialog.value = false; editingId.value = ''; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container { padding: 4px; }.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }.page-header h3 { margin: 0; }</style>
