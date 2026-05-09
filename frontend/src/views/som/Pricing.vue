<template>
  <div class="page-container">
    <el-card shadow="never"><div class="page-header"><h3>自动定价</h3><el-button type="primary" @click="runPricing"><el-icon><MagicStick /></el-icon>执行定价优化</el-button></div></el-card>
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="14"><el-card shadow="hover"><template #header><span>定价建议</span></template>
        <el-table :data="pricingData" stripe size="small">
          <el-table-column prop="sku" label="SKU" width="120" /><el-table-column prop="current_price" label="当前价格" width="100" /><el-table-column prop="suggested_price" label="建议价格" width="100" /><el-table-column prop="min_price" label="最低价" width="100" /><el-table-column prop="competitor_price" label="竞品价" width="100" /><el-table-column label="操作" width="80"><template #default="{ row }"><el-button link type="primary" size="small" @click="applyPrice(row)">应用</el-button></template></el-table-column>
        </el-table>
      </el-card></el-col>
      <el-col :span="10"><el-card shadow="hover"><template #header><span>定价策略</span></template>
        <el-form label-width="100px">
          <el-form-item label="策略类型"><el-select v-model="strategy.type"><el-option label="竞争定价" value="competitive" /><el-option label="利润优先" value="profit" /><el-option label="销量优先" value="volume" /></el-select></el-form-item>
          <el-form-item label="最低利润率"><el-input-number v-model="strategy.min_margin" :min="1" :max="50" /></el-form-item>
          <el-form-item label="调价幅度"><el-input-number v-model="strategy.max_adjust_pct" :min="1" :max="30" /></el-form-item>
          <el-form-item><el-button type="primary" @click="saveStrategy">保存策略</el-button></el-form-item>
        </el-form>
      </el-card></el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { somApi } from '@/api'
import { ElMessage } from 'element-plus'

const pricingData = ref<any[]>([])
const strategy = reactive({ type: 'competitive', min_margin: 15, max_adjust_pct: 10 })

async function runPricing() { try { const res: any = await somApi.optimizePricing({}); pricingData.value = res.data?.suggestions || []; ElMessage.success('定价优化完成') } catch { ElMessage.error('优化失败') } }
async function applyPrice(row: any) { await somApi.updateListingPrice(row.id, { price: row.suggested_price }); ElMessage.success('价格已更新'); row.current_price = row.suggested_price }
function saveStrategy() { ElMessage.success('策略已保存') }
</script>

<style scoped>.page-container{padding:4px}.page-header{display:flex;justify-content:space-between;align-items:center}.page-header h3{margin:0}</style>
