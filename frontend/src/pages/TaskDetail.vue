<template>
  <div class="task-detail">
    <el-card v-if="task">
      <template #header>
        <div class="card-header">
          <span>{{ t('task.detail') }}: {{ task.task_id }}</span>
          <el-button @click="$router.push('/tasks')">{{ t('common.back') }}</el-button>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('task.taskId')">{{ task.task_id }}</el-descriptions-item>
        <el-descriptions-item :label="t('task.status')">
          <el-tag :type="getStatusType(task.status)">{{ t(`status.${task.status}`) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.instruction')">{{ task.instruction }}</el-descriptions-item>
        <el-descriptions-item :label="t('task.device')">{{ task.device_id }}</el-descriptions-item>
        <el-descriptions-item :label="t('task.progress')">
          <el-progress
            :percentage="getProgress(task)"
            :status="getProgressStatus(task.status)"
          />
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.duration')">
          {{ task.duration_ms ? `${(task.duration_ms / 1000).toFixed(1)}s` : '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.errorType')" v-if="task.error_type">
          {{ task.error_type }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.errorMessage')" v-if="task.error_message">
          {{ task.error_message }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.createdAt')">
          {{ formatDate(task.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.report')" v-if="task.report_url">
          <el-button type="primary" size="small" @click="viewReport">{{ t('task.viewReport') }}</el-button>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="task?.steps?.length" style="margin-top: 20px">
      <template #header>
        <span>{{ t('task.steps') }}</span>
      </template>
      <el-table :data="task.steps" style="width: 100%">
        <el-table-column prop="step_index" :label="t('task.stepIndex')" width="60" />
        <el-table-column prop="action" :label="t('task.action')" width="120" />
        <el-table-column prop="target" :label="t('task.target')" />
        <el-table-column prop="value" :label="t('task.value')" />
        <el-table-column prop="status" :label="t('task.stepStatus')" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ t(`status.${row.status}`) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="retry_count" :label="t('task.retries')" width="80" />
        <el-table-column prop="duration_ms" :label="t('task.duration')" width="100">
          <template #default="{ row }">
            {{ row.duration_ms ? `${(row.duration_ms / 1000).toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column :label="t('task.screenshot')" width="150">
          <template #default="{ row }">
            <span v-if="row.screenshot_before || row.screenshot_after">
              <el-button size="small" link @click="viewScreenshot(row.screenshot_before)">{{ t('task.before') }}</el-button>
              <el-button size="small" link @click="viewScreenshot(row.screenshot_after)">{{ t('task.after') }}</el-button>
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
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useTaskStore } from '@/stores/task'

const { t } = useI18n()
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
