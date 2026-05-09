<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>店铺管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新增店铺</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="store_name" label="店铺名称" min-width="180" /><el-table-column prop="platform" label="平台" width="100" /><el-table-column prop="marketplace" label="站点" width="100" /><el-table-column prop="seller_id" label="卖家ID" width="140" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">{{ row.status === 'active' ? '正常' : '异常' }}</el-tag></template></el-table-column><el-table-column prop="sync_status" label="同步状态" width="100"><template #default="{ row }"><el-tag :type="row.sync_status === 'synced' ? 'success' : 'warning'" size="small">{{ row.sync_status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="syncStore(row)">同步</el-button></template></el-table-column>
    </el-table></el-card>
    <el-dialog v-model="showDialog" title="新增店铺" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="店铺名称"><el-input v-model="form.store_name" /></el-form-item><el-form-item label="平台"><el-select v-model="form.platform"><el-option label="Amazon" value="amazon" /><el-option label="Shopify" value="shopify" /><el-option label="eBay" value="ebay" /></el-select></el-form-item><el-form-item label="站点"><el-input v-model="form.marketplace" placeholder="如 US, UK, DE" /></el-form-item><el-form-item label="卖家ID"><el-input v-model="form.seller_id" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { somApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const showDialog = ref(false)
const form = reactive({ store_name: '', platform: 'amazon', marketplace: 'US', seller_id: '' })

async function loadData() { loading.value = true; try { const res: any = await somApi.listStores({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
async function syncStore(row: any) { await somApi.syncStore(row.id); ElMessage.success('同步已触发') }
async function submitForm() { await somApi.createStore(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
