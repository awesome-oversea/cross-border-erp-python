<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>询价管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建询价</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="inquiry_no" label="询价单号" min-width="160" /><el-table-column prop="title" label="询价标题" min-width="200" /><el-table-column prop="supplier_name" label="供应商" width="150" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="deadline" label="截止时间" width="170" />
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" title="新建询价" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item><el-form-item label="供应商"><el-select v-model="form.supplier_id"><el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" /></el-select></el-form-item><el-form-item label="截止时间"><el-date-picker v-model="form.deadline" type="datetime" /></el-form-item>
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
const form = reactive({ title: '', supplier_id: '', deadline: '' })

async function loadData() { loading.value = true; try { const res: any = await scmApi.listInquiries({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function loadSuppliers() { try { const res: any = await scmApi.listSuppliers({}); suppliers.value = res.data?.items || [] } catch {} }
async function submitForm() { await scmApi.createInquiry(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(() => { loadData(); loadSuppliers() })
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
