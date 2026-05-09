<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>SKU管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增SKU</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="sku_code" label="SKU编码" min-width="140" /><el-table-column prop="spu_name" label="SPU" min-width="180" /><el-table-column prop="attributes" label="属性" min-width="200" show-overflow-tooltip /><el-table-column prop="cost_price" label="成本价" width="100" /><el-table-column prop="weight" label="重量(g)" width="100" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="editRow(row)">编辑</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" :title="editingId ? '编辑SKU' : '新增SKU'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="SKU编码"><el-input v-model="form.sku_code" /></el-form-item><el-form-item label="SPU ID"><el-input v-model="form.spu_id" /></el-form-item><el-form-item label="属性"><el-input v-model="form.attributes" type="textarea" placeholder='{"color":"red","size":"M"}' /></el-form-item><el-form-item label="成本价"><el-input-number v-model="form.cost_price" :min="0" :precision="2" /></el-form-item><el-form-item label="重量(g)"><el-input-number v-model="form.weight" :min="0" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { pdmApi } from '@/api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false); const editingId = ref('')
const form = reactive({ sku_code: '', spu_id: '', attributes: '', cost_price: 0, weight: 0 })

async function loadData() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (route.query.spu_id) params.spu_id = route.query.spu_id
    const res: any = await pdmApi.listSKUs(params); tableData.value = res.data?.items || []; total.value = res.data?.total || 0
  } finally { loading.value = false }
}
function editRow(row: any) { editingId.value = row.id; Object.assign(form, row); showDialog.value = true }
async function submitForm() { if (editingId.value) { await pdmApi.updateSKU(editingId.value, form) } else { await pdmApi.createSKU(form) }; ElMessage.success('操作成功'); showDialog.value = false; editingId.value = ''; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
