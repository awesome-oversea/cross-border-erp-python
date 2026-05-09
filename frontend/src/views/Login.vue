<template>
  <div class="login-page">
    <div class="login-card">
      <h2 class="login-title">跨境电商ERP</h2>
      <p class="login-subtitle">Cross-border E-commerce ERP Platform</p>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="租户ID">
          <el-input v-model="form.tenantId" placeholder="请输入租户ID" prefix-icon="OfficeBuilding" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" native-type="submit" style="width: 100%">登 录</el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
/** 登录表单数据: 默认填充开发/演示环境凭据 */
const form = reactive({ tenantId: '10a8a067-5004-417d-900c-f248a30d91fe', username: 'admin', password: 'Admin@123' })

/**
 * 处理登录提交
 *
 * 校验表单完整性 -> 调用认证 Store 的 login 方法 -> 成功跳转首页/失败提示
 */
async function handleLogin() {
  if (!form.tenantId || !form.username || !form.password) {
    ElMessage.warning('请填写完整登录信息')
    return
  }
  loading.value = true
  try {
    const ok = await auth.login(form.username, form.password, form.tenantId)
    if (ok) {
      ElMessage.success('登录成功')
      router.push('/')
    } else {
      ElMessage.error('登录失败,请检查租户/用户名/密码')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.login-card { width: 400px; padding: 40px; background: #fff; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.15); }
.login-title { text-align: center; margin: 0 0 8px; font-size: 28px; color: #303133; }
.login-subtitle { text-align: center; margin: 0 0 32px; color: #909399; font-size: 14px; }
</style>
