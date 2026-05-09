<template>
  <div class="dashboard">
    <header class="dashboard-header">
      <h1>经营看板</h1>
      <div class="header-actions">
        <el-tag type="success" effect="dark">已连接</el-tag>
        <el-button type="primary" @click="refresh">刷新</el-button>
      </div>
    </header>

    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6" v-for="card in statCards" :key="card.title">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
            <div class="stat-label">{{ card.title }}</div>
            <div class="stat-trend" :class="card.trend > 0 ? 'up' : 'down'">
              {{ card.trend > 0 ? '↑' : '↓' }} {{ Math.abs(card.trend) }}%
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px;">
      <el-col :span="12">
        <el-card>
          <template #header>待办事项</template>
          <div v-if="todos.length === 0" class="empty-state">暂无待办事项</div>
          <div v-else>
            <div v-for="todo in todos" :key="todo.id" class="todo-item">
              <el-tag :type="todo.type" size="small">{{ todo.type }}</el-tag>
              <span class="todo-text">{{ todo.text }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>快捷入口</template>
          <el-row :gutter="12">
            <el-col :span="8" v-for="item in quickLinks" :key="item.name">
              <el-button class="quick-link" text>{{ item.name }}</el-button>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const statCards = ref([
  { title: '今日订单', value: '128', color: '#409eff', trend: 12 },
  { title: '销售额', value: '¥45,230', color: '#67c23a', trend: 8 },
  { title: '待发货', value: '23', color: '#e6a23c', trend: -5 },
  { title: '库存预警', value: '7', color: '#f56c6c', trend: 15 },
])

const todos = ref([
  { id: 1, type: '审核', text: '3笔采购单待审批', typeLabel: 'warning' },
  { id: 2, type: '发货', text: '23笔订单待发货', typeLabel: 'primary' },
  { id: 3, type: '告警', text: '5个SKU库存低于安全值', typeLabel: 'danger' },
])

const quickLinks = ref(
  ['订单管理', '库存查询', '采购下单', 'Listing管理', '广告管理', '财务报表'].map(n => ({ name: n }))
)

function refresh() {
  console.log('refresh')
}
</script>

<style scoped>
.dashboard { padding: 24px; }
.dashboard-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.dashboard-header h1 { margin: 0; font-size: 24px; }
.header-actions { display: flex; gap: 12px; }
.stat-cards { margin-bottom: 0; }
.stat-card { text-align: center; padding: 8px; }
.stat-value { font-size: 32px; font-weight: bold; }
.stat-label { font-size: 14px; color: #666; margin-top: 4px; }
.stat-trend { font-size: 12px; margin-top: 4px; }
.stat-trend.up { color: #67c23a; }
.stat-trend.down { color: #f56c6c; }
.empty-state { text-align: center; color: #999; padding: 24px; }
.todo-item { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.todo-item:last-child { border-bottom: none; }
.todo-text { font-size: 14px; }
.quick-link { width: 100%; margin-bottom: 8px !important; }
</style>
