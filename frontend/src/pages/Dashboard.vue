<template>
  <div class="dashboard">
    <el-container>
      <el-header>
        <div class="header-content">
          <h2>APP Automated Testing Platform</h2>
          <div class="user-info">
            <span>{{ username }}</span>
            <el-button type="danger" size="small" @click="handleLogout">Logout</el-button>
          </div>
        </div>
      </el-header>
      <el-container>
        <el-aside width="200px">
          <el-menu :default-active="activeMenu" router>
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/instruction">
              <el-icon><Edit /></el-icon>
              <span>Instruction Input</span>
            </el-menu-item>
            <el-menu-item index="/scripts">
              <el-icon><Document /></el-icon>
              <span>Scripts</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><List /></el-icon>
              <span>Tasks</span>
            </el-menu-item>
            <el-menu-item index="/devices">
              <el-icon><Monitor /></el-icon>
              <span>Devices</span>
            </el-menu-item>
            <el-menu-item index="/reports">
              <el-icon><DataAnalysis /></el-icon>
              <span>Reports</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main>
          <el-row :gutter="20">
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-value">{{ stats.totalTasks }}</div>
                <div class="stat-label">Total Tasks</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-value">{{ stats.runningTasks }}</div>
                <div class="stat-label">Running</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-value">{{ stats.completedTasks }}</div>
                <div class="stat-label">Completed</div>
              </el-card>
            </el-col>
            <el-col :span="6">
              <el-card class="stat-card">
                <div class="stat-value">{{ stats.failedTasks }}</div>
                <div class="stat-label">Failed</div>
              </el-card>
            </el-col>
          </el-row>

          <el-card class="recent-tasks" style="margin-top: 20px">
            <template #header>
              <div class="card-header">
                <span>Recent Tasks</span>
                <el-button type="primary" size="small" @click="$router.push('/tasks')">
                  View All
                </el-button>
              </div>
            </template>
            <el-table :data="recentTasks" style="width: 100%">
              <el-table-column prop="task_id" label="Task ID" width="150" />
              <el-table-column prop="instruction" label="Instruction" />
              <el-table-column prop="status" label="Status" width="100">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Progress" width="150">
                <template #default="{ row }">
                  <el-progress
                    :percentage="getProgress(row)"
                    :status="getProgressStatus(row.status)"
                  />
                </template>
              </el-table-column>
              <el-table-column label="Actions" width="100">
                <template #default="{ row }">
                  <el-button type="primary" size="small" link @click="viewTask(row.task_id)">
                    View
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useTaskStore } from '@/stores/task'
import { HomeFilled, Edit, Document, List, Monitor, DataAnalysis } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const taskStore = useTaskStore()

const username = computed(() => userStore.username)
const activeMenu = ref('/')

const stats = computed(() => ({
  totalTasks: taskStore.tasks.length,
  runningTasks: taskStore.runningTasks.length,
  completedTasks: taskStore.completedTasks.length,
  failedTasks: taskStore.failedTasks.length,
}))

const recentTasks = computed(() => taskStore.tasks.slice(0, 5))

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    pending: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
  }
  return types[status] || 'info'
}

const getProgress = (task: any) => {
  if (task.total_steps === 0) return 0
  return Math.round((task.completed_steps / task.total_steps) * 100)
}

const getProgressStatus = (status: string) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return undefined
}

const viewTask = (taskId: string) => {
  router.push(`/tasks/${taskId}`)
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}

onMounted(() => {
  taskStore.fetchTasks()
})
</script>

<style scoped>
.dashboard {
  height: 100vh;
}

.el-container {
  height: 100%;
}

.el-header {
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
  font-size: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.el-aside {
  background: #f5f7fa;
}

.el-main {
  background: #f0f2f5;
  padding: 20px;
}

.stat-card {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  margin-top: 10px;
  color: #666;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
