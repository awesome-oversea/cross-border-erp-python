<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>工作流管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建工作流</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="name" label="工作流名称" min-width="200" /><el-table-column prop="trigger_type" label="触发类型" width="120" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="run_count" label="执行次数" width="100" /><el-table-column prop="last_run_at" label="最近执行" width="170" /><el-table-column prop="updated_at" label="更新时间" width="170" />
      <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="triggerWorkflow(row)">手动触发</el-button><el-button link type="primary" size="small" @click="editWorkflow(row)">编辑</el-button></template></el-table-column>
    </el-table></el-card>
    <el-dialog v-model="showDialog" title="新建工作流" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="触发类型"><el-select v-model="form.trigger_type"><el-option label="事件触发" value="event" /><el-option label="定时触发" value="schedule" /><el-option label="手动触发" value="manual" /></el-select></el-form-item><el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { sysApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const showDialog = ref(false)
const form = reactive({ name: '', trigger_type: 'event', description: '' })

async function loadData() { loading.value = true; try { const res: any = await sysApi.listWorkflows({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
async function triggerWorkflow(row: any) { await sysApi.triggerWorkflow(row.id); ElMessage.success('已触发') }
function editWorkflow(row: any) { ElMessage.info(`编辑工作流: ${row.name}`) }
async function submitForm() { await sysApi.createWorkflow(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
