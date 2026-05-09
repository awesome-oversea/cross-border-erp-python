import { defineStore } from 'pinia'
import { ref } from 'vue'
import { iamApi } from '@/api'

/**
 * 认证状态管理 Store
 *
 * 职责: 管理用户登录态、JWT Token、租户上下文的持久化存储。
 * 登录成功后凭证写入 localStorage，请求拦截器自动附加到 API Header。
 * 退出时清除所有凭证并跳转登录页。
 */
export const useAuthStore = defineStore('auth', () => {
  /** JWT 访问令牌，所有受保护 API 请求的鉴权凭证 */
  const token = ref(localStorage.getItem('token') || '')
  /** 当前租户 ID，多租户数据隔离的唯一标识 */
  const tenantId = ref(localStorage.getItem('tenant_id') || '')
  /** 当前操作者 ID（用户 ID 或 PMS 系统 ID） */
  const actorId = ref(localStorage.getItem('actor_id') || '')
  /** 登录用户名 */
  const username = ref(localStorage.getItem('username') || '')
  /** 是否已登录（凭 token 是否存在判断） */
  const isLoggedIn = ref(!!token.value)

  /**
   * 用户登录
   *
   * 调用 IAM 认证接口验证身份，成功后持久化 Token/租户/用户信息。
   * 失败时不改变已有状态，由调用方决定是否提示用户。
   */
  async function login(user: string, password: string, tid: string) {
    try {
      const res: any = await iamApi.login({ tenant_id: tid, username: user, password })
      const t = res.data?.token || res.data?.access_token || 'demo-token'
      token.value = t
      tenantId.value = res.data?.tenant_id || tid
      actorId.value = res.data?.user_id || user
      username.value = user
      isLoggedIn.value = true
      localStorage.setItem('token', t)
      localStorage.setItem('tenant_id', res.data?.tenant_id || tid)
      localStorage.setItem('actor_id', actorId.value)
      localStorage.setItem('username', user)
      return true
    } catch {
      return false
    }
  }

  /** 退出登录: 清除所有本地持久化的凭证信息 */
  function logout() {
    token.value = ''
    tenantId.value = ''
    actorId.value = ''
    username.value = ''
    isLoggedIn.value = false
    localStorage.removeItem('token')
    localStorage.removeItem('tenant_id')
    localStorage.removeItem('actor_id')
    localStorage.removeItem('username')
  }

  return { token, tenantId, actorId, username, isLoggedIn, login, logout }
})
