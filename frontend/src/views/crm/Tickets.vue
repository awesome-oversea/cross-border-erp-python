<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>工单管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建工单</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="ticket_no" label="工单号" min-width="140" /><el-table-column prop="subject" label="主题" min-width="200" /><el-table-column prop="customer_name" label="客户" width="120" /><el-table-column prop="priority" label="优先级" width="100"><template #default="{ row }"><el-tag :type="row.priority === 'high' ? 'danger' : row.priority === 'medium' ? 'warning' : 'info'" size="small">{{ row.priority }}</el-tag></template></el-table-column><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="assignee" label="处理人" width="100" /><el-table-column prop="created_at" label="创建时间" width="170" />
      <el-table-column label="操作" width="100" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="handleTicket(row)">处理</el-button></template></el-table-column>
    </el-table></el-card>
    <el-dialog v-model="showDialog" title="新建工单" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="主题"><el-input v-model="form.subject" /></el-form-item><el-form-item label="客户ID"><el-input v-model="form.customer_id" /></el-form-item><el-form-item label="优先级"><el-select v-model="form.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item><el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { crmApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const showDialog = ref(false)
const form = reactive({ subject: '', customer_id: '', priority: 'medium', description: '' })

async function loadData() { loading.value = true; try { const res: any = await crmApi.listTickets({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
function handleTicket(row: any) { ElMessage.info(`处理工单: ${row.ticket_no}`) }
async function submitForm() { await crmApi.createTicket(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
