<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.totalTasks }}</div>
          <div class="stat-label">{{ t('dashboard.totalTasks') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.runningTasks }}</div>
          <div class="stat-label">{{ t('dashboard.runningTasks') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.completedTasks }}</div>
          <div class="stat-label">{{ t('dashboard.completedTasks') }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.failedTasks }}</div>
          <div class="stat-label">{{ t('dashboard.failedTasks') }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="recent-tasks" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>{{ t('dashboard.recentTasks') }}</span>
          <el-button type="primary" size="small" @click="$router.push('/tasks')">
            {{ t('dashboard.viewAll') }}
          </el-button>
        </div>
      </template>
      <el-table :data="recentTasks" style="width: 100%">
        <el-table-column prop="task_id" :label="t('task.taskId')" width="150" />
        <el-table-column prop="instruction" :label="t('task.instruction')" />
        <el-table-column prop="status" :label="t('task.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ t(`status.${row.status}`) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('task.progress')" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="getProgress(row)"
              :status="getProgressStatus(row.status)"
            />
          </template>
        </el-table-column>
        <el-table-column :label="t('task.actions')" width="100">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="viewTask(row.task_id)">
              {{ t('task.view') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTaskStore } from '@/stores/task'

const { t } = useI18n()
const router = useRouter()
const taskStore = useTaskStore()

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

onMounted(() => {
  taskStore.fetchTasks()
})
</script>

<style scoped>
.dashboard {
  height: 100%;
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
