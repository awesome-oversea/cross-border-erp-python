import axios, { type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const tenantId = localStorage.getItem('tenant_id') || ''
  const actorId = localStorage.getItem('actor_id') || ''
  const token = localStorage.getItem('token') || ''
  if (tenantId) config.headers['X-Tenant-ID'] = tenantId
  if (actorId) config.headers['X-Actor-ID'] = actorId
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  config.headers['X-Trace-ID'] = crypto.randomUUID()
  return config
})

api.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    if (data.code && data.code !== 0 && data.code !== 200) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    ElMessage.error(error.response?.data?.message || error.message || '网络错误')
    return Promise.reject(error)
  }
)

export default api

export const buildQuery = (params: Record<string, any>): string => {
  const usp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') usp.set(k, String(v))
  })
  return usp.toString() ? `?${usp.toString()}` : ''
}
