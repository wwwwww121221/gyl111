import axios from 'axios'
import { ElMessage } from 'element-plus'

const clearAuthStorage = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('department')
  localStorage.removeItem('username')
  localStorage.removeItem('supplier_id')
  localStorage.removeItem('supplier_name')
  localStorage.removeItem('supplier_status')
  localStorage.removeItem('member_status')
}

const getLoginRoute = () => '/#/login'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export const getApiOrigin = () => {
  if (typeof window === 'undefined') return ''
  const configuredOrigin = String(import.meta.env.VITE_API_URL || '').trim().replace(/\/$/, '')
  if (configuredOrigin) return configuredOrigin
  if (import.meta.env.DEV) {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return window.location.origin.replace(/\/$/, '')
}

const getAssetOrigin = () => {
  if (typeof window === 'undefined') return ''
  if (import.meta.env.DEV) {
    return `${window.location.protocol}//${window.location.hostname}:8000`
  }
  return ''
}

export const resolveAssetUrl = (path) => {
  const normalized = String(path || '').trim()
  if (!normalized) return ''
  if (/^https?:\/\//i.test(normalized) || normalized.startsWith('blob:') || normalized.startsWith('data:')) {
    return normalized
  }
  if (normalized.startsWith('/static/')) {
    return `${getAssetOrigin()}${normalized}`
  }
  return normalized
}

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.config?.silentError) {
      return Promise.reject(error)
    }

    if (error.response) {
      if (error.response.status === 401) {
        clearAuthStorage()
        ElMessage.error('登录已失效，请重新登录')
        window.location.replace(getLoginRoute())
      } else {
        ElMessage.error(error.response.data.error || error.response.data.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络错误或服务不可用')
    }
    return Promise.reject(error)
  },
)

export default api
