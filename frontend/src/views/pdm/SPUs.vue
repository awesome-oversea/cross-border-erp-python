<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>SPU管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增SPU</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="spu_code" label="SPU编码" min-width="140" /><el-table-column prop="name" label="产品名称" min-width="200" /><el-table-column prop="category" label="分类" width="120" /><el-table-column prop="brand" label="品牌" width="120" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="sku_count" label="SKU数" width="80" />
      <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="editRow(row)">编辑</el-button><el-button link type="primary" size="small" @click="viewSKUs(row)">SKU</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" :title="editingId ? '编辑SPU' : '新增SPU'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="SPU编码"><el-input v-model="form.spu_code" /></el-form-item><el-form-item label="产品名称"><el-input v-model="form.name" /></el-form-item><el-form-item label="分类"><el-input v-model="form.category" /></el-form-item><el-form-item label="品牌"><el-input v-model="form.brand" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { pdmApi } from '@/api'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false); const editingId = ref('')
const form = reactive({ spu_code: '', name: '', category: '', brand: '' })

async function loadData() { loading.value = true; try { const res: any = await pdmApi.listSPUs({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
function editRow(row: any) { editingId.value = row.id; Object.assign(form, row); showDialog.value = true }
function viewSKUs(row: any) { router.push({ path: '/pdm/skus', query: { spu_id: row.id } }) }
async function submitForm() { if (editingId.value) { await pdmApi.updateSPU(editingId.value, form) } else { await pdmApi.createSPU(form) }; ElMessage.success('操作成功'); showDialog.value = false; editingId.value = ''; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
