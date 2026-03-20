<template>
  <div class="task-detail">
    <el-card v-if="task">
      <template #header>
        <div class="card-header">
          <span>Task: {{ task.task_id }}</span>
          <el-button @click="$router.push('/tasks')">Back</el-button>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="Task ID">{{ task.task_id }}</el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag :type="getStatusType(task.status)">{{ task.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Instruction">{{ task.instruction }}</el-descriptions-item>
        <el-descriptions-item label="Device">{{ task.device_id }}</el-descriptions-item>
        <el-descriptions-item label="Progress">
          <el-progress
            :percentage="getProgress(task)"
            :status="getProgressStatus(task.status)"
          />
        </el-descriptions-item>
        <el-descriptions-item label="Duration">
          {{ task.duration_ms ? `${(task.duration_ms / 1000).toFixed(1)}s` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="Error Type" v-if="task.error_type">
          {{ task.error_type }}
        </el-descriptions-item>
        <el-descriptions-item label="Error Message" v-if="task.error_message">
          {{ task.error_message }}
        </el-descriptions-item>
        <el-descriptions-item label="Created At">
          {{ formatDate(task.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="Report" v-if="task.report_url">
          <el-button type="primary" size="small" @click="viewReport">View Report</el-button>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="task?.steps?.length" style="margin-top: 20px">
      <template #header>
        <span>Task Steps</span>
      </template>
      <el-table :data="task.steps" style="width: 100%">
        <el-table-column prop="step_index" label="#" width="60" />
        <el-table-column prop="action" label="Action" width="120" />
        <el-table-column prop="target" label="Target" />
        <el-table-column prop="value" label="Value" />
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="retry_count" label="Retries" width="80" />
        <el-table-column prop="duration_ms" label="Duration" width="100">
          <template #default="{ row }">
            {{ row.duration_ms ? `${(row.duration_ms / 1000).toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Screenshots" width="150">
          <template #default="{ row }">
            <span v-if="row.screenshot_before || row.screenshot_after">
              <el-button size="small" link @click="viewScreenshot(row.screenshot_before)">Before</el-button>
              <el-button size="small" link @click="viewScreenshot(row.screenshot_after)">After</el-button>
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-skeleton v-if="loading" style="margin-top: 20px" :rows="5" animated />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useTaskStore } from '@/stores/task'

const route = useRoute()
const taskStore = useTaskStore()

const loading = computed(() => taskStore.loading)
const task = computed(() => taskStore.currentTask)

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

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const viewReport = () => {
  if (task.value?.report_url) {
    window.open(task.value.report_url, '_blank')
  }
}

const viewScreenshot = (url: string) => {
  if (url) {
    window.open(url, '_blank')
  }
}

onMounted(() => {
  const taskId = route.params.id as string
  taskStore.fetchTask(taskId)
})
</script>

<style scoped>
.task-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
