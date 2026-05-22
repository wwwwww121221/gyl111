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

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

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
    if (error.response) {
      if (error.response.status === 401) {
        clearAuthStorage()
        ElMessage.error('登录已过期，请重新登录')
        window.location.href = '/login'
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
