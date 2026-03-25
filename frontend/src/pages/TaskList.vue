<template>
  <div class="task-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ t('task.list') }}</span>
          <el-button type="primary" @click="$router.push('/instruction')">
            {{ t('task.newTask') }}
          </el-button>
        </div>
      </template>
      <el-table :data="tasks" v-loading="loading" style="width: 100%">
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
        <el-table-column prop="device_id" :label="t('task.device')" width="120" />
        <el-table-column :label="t('task.duration')" width="100">
          <template #default="{ row }">
            {{ row.duration_ms ? `${(row.duration_ms / 1000).toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('task.createdAt')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('task.actions')" width="120">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="viewTask(row.task_id)">
              {{ t('task.view') }}
            </el-button>
            <el-button type="danger" size="small" link @click="handleDelete(row.task_id)">
              {{ t('task.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 20px"
        @current-change="handlePageChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskStore } from '@/stores/task'

const { t } = useI18n()
const router = useRouter()
const taskStore = useTaskStore()

const currentPage = ref(1)
const pageSize = ref(20)

const tasks = computed(() => taskStore.tasks)
const loading = computed(() => taskStore.loading)
const total = computed(() => taskStore.total)

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

const viewTask = (taskId: string) => {
  router.push(`/tasks/${taskId}`)
}

const handleDelete = async (taskId: string) => {
  try {
    await ElMessageBox.confirm(t('task.deleteConfirm'), t('common.warning'), {
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
    await taskStore.deleteTask(taskId)
    ElMessage.success(t('task.deleteSuccess'))
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(t('task.deleteFailed'))
    }
  }
}

const handlePageChange = (page: number) => {
  taskStore.fetchTasks((page - 1) * pageSize.value, pageSize.value)
}

onMounted(() => {
  taskStore.fetchTasks()
})
</script>

<style scoped>
.task-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
