<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>物流管理</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建物流单</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="shipment_no" label="物流单号" min-width="160" /><el-table-column prop="carrier" label="承运商" width="120" /><el-table-column prop="channel" label="渠道" width="120" /><el-table-column prop="origin" label="始发地" width="120" /><el-table-column prop="destination" label="目的地" width="120" /><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'delivered' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag></template></el-table-column><el-table-column prop="created_at" label="创建时间" width="170" />
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" title="新建物流单" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="承运商"><el-select v-model="form.carrier"><el-option label="DHL" value="dhl" /><el-option label="FedEx" value="fedex" /><el-option label="UPS" value="ups" /><el-option label="FBA" value="fba" /></el-select></el-form-item><el-form-item label="渠道"><el-input v-model="form.channel" /></el-form-item><el-form-item label="目的地"><el-input v-model="form.destination" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { tmsApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false)
const form = reactive({ carrier: 'dhl', channel: '', destination: '' })

async function loadData() { loading.value = true; try { const res: any = await tmsApi.listShipments({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function submitForm() { await tmsApi.createShipment(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
