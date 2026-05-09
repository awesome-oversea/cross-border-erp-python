<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>FBA货件</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建货件</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="shipment_id" label="货件ID" min-width="140" /><el-table-column prop="fba_shipment_id" label="FBA货件号" min-width="160" /><el-table-column prop="destination" label="目的仓库" width="140" /><el-table-column prop="total_units" label="总数量" width="100" /><el-table-column prop="status" label="状态" width="120"><template #default="{ row }"><el-tag :type="fbaStatusType(row.status)" size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="created_at" label="创建时间" width="170" />
    </el-table></el-card>
    <el-dialog v-model="showDialog" title="新建FBA货件" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="目的仓库"><el-input v-model="form.destination" /></el-form-item><el-form-item label="总数量"><el-input-number v-model="form.total_units" :min="1" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { fbaApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const showDialog = ref(false)
const form = reactive({ destination: '', total_units: 1 })

function fbaStatusType(s: string) { return s === 'CLOSED' ? 'success' : s === 'SHIPPED' ? '' : s === 'RECEIVING' ? 'warning' : 'info' }
async function loadData() { loading.value = true; try { const res: any = await fbaApi.listShipments({}); tableData.value = res.data?.items || [] } finally { loading.value = false } }
async function submitForm() { await fbaApi.createShipment(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
