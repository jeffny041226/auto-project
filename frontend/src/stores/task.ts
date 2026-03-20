import { defineStore } from 'pinia'
import { tasksApi } from '@/api'

interface TaskStep {
  step_id: string
  step_index: number
  action: string
  target: string
  value: string
  status: string
  screenshot_before?: string
  screenshot_after?: string
  retry_count: number
  duration_ms?: number
  error_detail?: string
}

interface Task {
  task_id: string
  instruction: string
  script_id: string
  device_id: string
  status: string
  total_steps: number
  completed_steps: number
  error_type?: string
  error_message?: string
  report_url?: string
  duration_ms?: number
  created_at: string
  steps?: TaskStep[]
}

interface TaskState {
  tasks: Task[]
  currentTask: Task | null
  total: number
  loading: boolean
}

export const useTaskStore = defineStore('task', {
  state: (): TaskState => ({
    tasks: [],
    currentTask: null,
    total: 0,
    loading: false,
  }),

  getters: {
    pendingTasks: (state) => state.tasks.filter((t) => t.status === 'pending'),
    runningTasks: (state) => state.tasks.filter((t) => t.status === 'running'),
    completedTasks: (state) => state.tasks.filter((t) => t.status === 'completed'),
    failedTasks: (state) => state.tasks.filter((t) => t.status === 'failed'),
  },

  actions: {
    async fetchTasks(skip = 0, limit = 20) {
      this.loading = true
      try {
        const response = await tasksApi.list(skip, limit)
        this.tasks = response.data.items
        this.total = response.data.total
      } finally {
        this.loading = false
      }
    },

    async fetchTask(taskId: string) {
      this.loading = true
      try {
        const response = await tasksApi.get(taskId)
        this.currentTask = response.data
        return this.currentTask
      } finally {
        this.loading = false
      }
    },

    async createTask(instruction: string, deviceId?: string) {
      const response = await tasksApi.create({
        instruction,
        device_id: deviceId,
      })
      const task = response.data
      this.tasks.unshift(task)
      return task
    },

    updateTaskInList(taskId: string, updates: Partial<Task>) {
      const index = this.tasks.findIndex((t) => t.task_id === taskId)
      if (index !== -1) {
        this.tasks[index] = { ...this.tasks[index], ...updates }
      }
      if (this.currentTask?.task_id === taskId) {
        this.currentTask = { ...this.currentTask, ...updates }
      }
    },
  },
})
