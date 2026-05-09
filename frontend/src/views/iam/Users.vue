<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header">
        <h3>用户管理</h3>
        <el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增用户</el-button>
      </div>
      <el-table :data="tableData" v-loading="loading" stripe>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="phone" label="手机号" min-width="130" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">{{ row.status === 'active' ? '启用' : '禁用' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="editRow(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="deleteRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top: 16px; justify-content: flex-end" />
    </el-card>
    <el-dialog v-model="showDialog" :title="editingId ? '编辑用户' : '新增用户'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="form.status"><el-option label="启用" value="active" /><el-option label="禁用" value="inactive" /></el-select></el-form-item>
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
const form = reactive({ username: '', email: '', phone: '', status: 'active' })

async function loadData() {
  loading.value = true
  try {
    const res: any = await iamApi.listUsers({ page: page.value, page_size: pageSize.value })
    tableData.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function editRow(row: any) {
  editingId.value = row.id
  Object.assign(form, row)
  showDialog.value = true
}

async function deleteRow(row: any) {
  await ElMessageBox.confirm(`确定删除用户 ${row.username}?`, '提示', { type: 'warning' })
  await iamApi.deleteUser(row.id)
  ElMessage.success('删除成功')
  loadData()
}

async function submitForm() {
  if (editingId.value) {
    await iamApi.updateUser(editingId.value, form)
  } else {
    await iamApi.createUser(form)
  }
  ElMessage.success(editingId.value ? '更新成功' : '创建成功')
  showDialog.value = false
  editingId.value = ''
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.page-container { padding: 4px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h3 { margin: 0; }
</style>
