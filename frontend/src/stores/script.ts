import { defineStore } from 'pinia'
import { scriptsApi } from '@/api'

interface Script {
  script_id: string
  intent: string
  structured_instruction: any
  pseudo_code?: string
  maestro_yaml?: string
  version: number
  hit_count: number
  status: string
  created_at: string
  updated_at: string
}

interface ScriptState {
  scripts: Script[]
  currentScript: Script | null
  total: number
  loading: boolean
}

export const useScriptStore = defineStore('script', {
  state: (): ScriptState => ({
    scripts: [],
    currentScript: null,
    total: 0,
    loading: false,
  }),

  actions: {
    async fetchScripts(skip = 0, limit = 20) {
      this.loading = true
      try {
        const response = await scriptsApi.list(skip, limit)
        this.scripts = response.data.items
        this.total = response.data.total
      } finally {
        this.loading = false
      }
    },

    async fetchScript(scriptId: string) {
      this.loading = true
      try {
        const response = await scriptsApi.get(scriptId)
        this.currentScript = response.data
        return this.currentScript
      } finally {
        this.loading = false
      }
    },

    async createScript(data: any) {
      const response = await scriptsApi.create(data)
      const script = response.data
      this.scripts.unshift(script)
      return script
    },

    async updateScript(scriptId: string, data: any) {
      const response = await scriptsApi.update(scriptId, data)
      const script = response.data
      const index = this.scripts.findIndex((s) => s.script_id === scriptId)
      if (index !== -1) {
        this.scripts[index] = script
      }
      if (this.currentScript?.script_id === scriptId) {
        this.currentScript = script
      }
      return script
    },

    async deleteScript(scriptId: string) {
      await scriptsApi.delete(scriptId)
      this.scripts = this.scripts.filter((s) => s.script_id !== scriptId)
    },
  },
})
