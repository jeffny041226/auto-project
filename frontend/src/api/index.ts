import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  async (error: AxiosError) => {
    if (error.response) {
      const status = error.response.status
      if (status === 401) {
        localStorage.removeItem('token')
        ElMessage.error('Authentication expired, please login again')
        router.push({ name: 'Login' })
      } else if (status === 403) {
        ElMessage.error('You do not have permission to perform this action')
      } else if (status === 404) {
        ElMessage.error('Resource not found')
      } else if (status >= 500) {
        ElMessage.error('Server error, please try again later')
      }
    } else if (error.request) {
      ElMessage.error('Network error, please check your connection')
    }
    return Promise.reject(error)
  }
)

export default api

// Auth API
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  register: (username: string, password: string, email?: string) =>
    api.post('/auth/register', { username, password, email }),
  refresh: (refreshToken: string) =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),
}

// Scripts API
export const scriptsApi = {
  list: (skip = 0, limit = 20) =>
    api.get('/scripts', { params: { skip, limit } }),
  get: (scriptId: string) =>
    api.get(`/scripts/${scriptId}`),
  create: (data: any) =>
    api.post('/scripts', data),
  update: (scriptId: string, data: any) =>
    api.put(`/scripts/${scriptId}`, data),
  delete: (scriptId: string) =>
    api.delete(`/scripts/${scriptId}`),
}

// Tasks API
export const tasksApi = {
  list: (skip = 0, limit = 20) =>
    api.get('/tasks', { params: { skip, limit } }),
  get: (taskId: string) =>
    api.get(`/tasks/${taskId}`),
  create: (data: any) =>
    api.post('/tasks', data),
  update: (taskId: string, data: any) =>
    api.patch(`/tasks/${taskId}`, data),
}

// Devices API
export const devicesApi = {
  list: (skip = 0, limit = 20) =>
    api.get('/devices', { params: { skip, limit } }),
  get: (deviceId: string) =>
    api.get(`/devices/${deviceId}`),
  create: (data: any) =>
    api.post('/devices', data),
  update: (deviceId: string, data: any) =>
    api.patch(`/devices/${deviceId}`, data),
}

// Reports API
export const reportsApi = {
  get: (reportId: string) =>
    api.get(`/reports/${reportId}`),
  download: (reportId: string) =>
    api.get(`/reports/${reportId}/download`, { responseType: 'blob' }),
}
