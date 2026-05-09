<template>
  <div class="page-container"><el-card shadow="never"><div class="page-header"><h3>广告活动</h3><el-button type="primary" @click="showDialog = true"><el-icon><Plus /></el-icon>新建活动</el-button></div>
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column prop="campaign_name" label="活动名称" min-width="200" /><el-table-column prop="platform" label="平台" width="100" /><el-table-column prop="campaign_type" label="类型" width="100" /><el-table-column prop="daily_budget" label="日预算" width="100"><template #default="{ row }">¥{{ row.daily_budget }}</template></el-table-column><el-table-column prop="spend" label="花费" width="100"><template #default="{ row }">¥{{ row.spend }}</template></el-table-column><el-table-column prop="acos" label="ACOS" width="100"><template #default="{ row }">{{ row.acos }}%</template></el-table-column><el-table-column prop="status" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" size="small" @click="toggleStatus(row)">{{ row.status === 'active' ? '暂停' : '启用' }}</el-button></template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, sizes, prev, pager, next" style="margin-top:16px;justify-content:flex-end" /></el-card>
    <el-dialog v-model="showDialog" title="新建广告活动" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="活动名称"><el-input v-model="form.campaign_name" /></el-form-item><el-form-item label="平台"><el-select v-model="form.platform"><el-option label="Amazon" value="amazon" /><el-option label="Shopify" value="shopify" /></el-select></el-form-item><el-form-item label="类型"><el-select v-model="form.campaign_type"><el-option label="SP" value="sp" /><el-option label="SB" value="sb" /><el-option label="SD" value="sd" /></el-select></el-form-item><el-form-item label="日预算"><el-input-number v-model="form.daily_budget" :min="1" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="showDialog = false">取消</el-button><el-button type="primary" @click="submitForm">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { adsApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const tableData = ref<any[]>([]); const page = ref(1); const pageSize = ref(20); const total = ref(0)
const showDialog = ref(false)
const form = reactive({ campaign_name: '', platform: 'amazon', campaign_type: 'sp', daily_budget: 50 })

async function loadData() { loading.value = true; try { const res: any = await adsApi.listCampaigns({ page: page.value, page_size: pageSize.value }); tableData.value = res.data?.items || []; total.value = res.data?.total || 0 } finally { loading.value = false } }
async function toggleStatus(row: any) { await adsApi.updateCampaign(row.id, { status: row.status === 'active' ? 'paused' : 'active' }); ElMessage.success('操作成功'); loadData() }
async function submitForm() { await adsApi.createCampaign(form); ElMessage.success('创建成功'); showDialog.value = false; loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}</style>
