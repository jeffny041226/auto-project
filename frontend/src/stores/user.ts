import { defineStore } from 'pinia'
import { authApi } from '@/api'

interface UserInfo {
  user_id: string
  username: string
  email: string
  role: string
  status: string
}

export const useUserStore = defineStore('user', {
  state: () => ({
    token: '',
    userInfo: null as UserInfo | null,
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    username: (state) => state.userInfo?.username || '',
    role: (state) => state.userInfo?.role || 'user',
  },

  actions: {
    async login(username: string, password: string) {
      const response = await authApi.login(username, password)
      const { access_token, refresh_token } = response.data
      this.token = access_token
      localStorage.setItem('token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      await this.fetchUserInfo()
    },

    async register(username: string, password: string, email?: string) {
      const response = await authApi.register(username, password, email)
      return response.data
    },

    async fetchUserInfo() {
      // In a real app, you'd have a /me endpoint
      // For now, decode from JWT or fetch from API
      try {
        const tokenParts = this.token.split('.')
        if (tokenParts.length === 3) {
          const payload = JSON.parse(atob(tokenParts[1]))
          this.userInfo = {
            user_id: payload.sub || '',
            username: payload.username || '',
            email: payload.email || '',
            role: payload.role || 'user',
            status: payload.status || 'active',
          }
        }
      } catch (e) {
        console.error('Failed to fetch user info', e)
      }
    },

    logout() {
      this.token = ''
      this.userInfo = null
      localStorage.removeItem('token')
      localStorage.removeItem('refresh_token')
    },
  },
})
