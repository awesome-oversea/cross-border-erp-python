<template>
  <div class="page-container">
    <el-card shadow="never">
      <div class="page-header"><h3>智能推荐</h3><el-button type="primary" @click="loadData"><el-icon><Refresh /></el-icon>刷新推荐</el-button></div>
      <el-row :gutter="16">
        <el-col :span="12" v-for="rec in recommendations" :key="rec.id">
          <el-card shadow="hover" class="rec-card">
            <div class="rec-header">
              <el-tag :type="rec.priority === 'high' ? 'danger' : rec.priority === 'medium' ? 'warning' : 'info'" size="small">{{ rec.priority }}</el-tag>
              <el-tag size="small">{{ rec.domain }}</el-tag>
            </div>
            <h4 class="rec-title">{{ rec.title }}</h4>
            <p class="rec-desc">{{ rec.description }}</p>
            <div class="rec-actions">
              <el-button type="primary" size="small" @click="applyRecommendation(rec)">应用</el-button>
              <el-button size="small" @click="dismissRecommendation(rec)">忽略</el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-empty v-if="!recommendations.length && !loading" description="暂无推荐" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { sysApi } from '@/api'
import { ElMessage } from 'element-plus'

const loading = ref(false); const recommendations = ref<any[]>([])

async function loadData() {
  loading.value = true
  try { const res: any = await sysApi.listRecommendations({}); recommendations.value = res.data?.items || [] } finally { loading.value = false }
}
async function applyRecommendation(rec: any) { await sysApi.applyRecommendation(rec.id); ElMessage.success('已应用推荐'); loadData() }
async function dismissRecommendation(rec: any) { await sysApi.dismissRecommendation(rec.id); ElMessage.info('已忽略'); loadData() }
onMounted(loadData)
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-header h3{margin:0}.rec-card{margin-bottom:16px}.rec-header{display:flex;gap:8px;margin-bottom:8px}.rec-title{margin:0 0 8px;font-size:15px}.rec-desc{margin:0 0 12px;font-size:13px;color:#606266}.rec-actions{display:flex;gap:8px}</style>
