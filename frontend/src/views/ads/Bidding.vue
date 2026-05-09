<template>
  <div class="page-container">
    <el-card shadow="never"><div class="page-header"><h3>智能竞价</h3><el-button type="primary" @click="runOptimization"><el-icon><MagicStick /></el-icon>执行优化</el-button></div></el-card>
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12"><el-card shadow="hover"><template #header><span>竞价优化建议</span></template>
        <el-table :data="suggestions" stripe size="small">
          <el-table-column prop="keyword" label="关键词" min-width="120" /><el-table-column prop="current_bid" label="当前竞价" width="100" /><el-table-column prop="suggested_bid" label="建议竞价" width="100" /><el-table-column prop="action" label="操作" width="80"><template #default="{ row }"><el-button link type="primary" size="small" @click="applyBid(row)">应用</el-button></template></el-table-column>
        </el-table>
      </el-card></el-col>
      <el-col :span="12"><el-card shadow="hover"><template #header><span>竞价策略</span></template>
        <el-form label-width="100px">
          <el-form-item label="策略类型"><el-select v-model="strategy.type"><el-option label="动态竞价-仅降低" value="dynamic_down" /><el-option label="动态竞价-升降" value="dynamic_up_down" /><el-option label="固定竞价" value="fixed" /></el-select></el-form-item>
          <el-form-item label="目标ACOS"><el-input-number v-model="strategy.target_acos" :min="1" :max="100" /></el-form-item>
          <el-form-item><el-button type="primary" @click="saveStrategy">保存策略</el-button></el-form-item>
        </el-form>
      </el-card></el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { adsApi } from '@/api'
import { ElMessage } from 'element-plus'

const suggestions = ref<any[]>([])
const strategy = reactive({ type: 'dynamic_down', target_acos: 25 })

async function runOptimization() { try { const res: any = await adsApi.optimizeBidding({}); suggestions.value = res.data?.suggestions || []; ElMessage.success('优化完成') } catch { ElMessage.error('优化失败') } }
async function applyBid(row: any) { await adsApi.updateKeyword(row.id, { bid: row.suggested_bid }); ElMessage.success('已应用'); row.current_bid = row.suggested_bid }
async function saveStrategy() { ElMessage.success('策略已保存') }
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center}.page-header h3{margin:0}</style>
