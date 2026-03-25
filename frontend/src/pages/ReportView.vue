<template>
  <div class="report-view">
    <el-card>
      <template #header>
        <span>{{ t('report.title') }}</span>
      </template>
      <el-table :data="reports" v-loading="loading" style="width: 100%">
        <el-table-column prop="report_id" :label="t('task.taskId')" width="150" />
        <el-table-column prop="task_id" :label="t('task.taskId')" width="150" />
        <el-table-column prop="status" :label="t('task.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'passed' ? 'success' : 'danger'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_steps" :label="t('task.steps')" width="100" />
        <el-table-column prop="passed_steps" :label="t('status.completed')" width="80" />
        <el-table-column prop="failed_steps" :label="t('status.failed')" width="80" />
        <el-table-column prop="duration_ms" :label="t('task.duration')" width="100">
          <template #default="{ row }">
            {{ row.duration_ms ? `${(row.duration_ms / 1000).toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('task.createdAt')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('task.actions')" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="viewReport(row.report_id)">
              {{ t('task.view') }}
            </el-button>
            <el-button type="success" size="small" link @click="downloadReport(row.report_id)">
              {{ t('report.download') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { reportsApi } from '@/api'

const { t } = useI18n()
const reports = ref<any[]>([])
const loading = ref(false)

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const viewReport = (reportId: string) => {
  window.open(`/reports/${reportId}`, '_blank')
}

const downloadReport = async (reportId: string) => {
  try {
    const response = await reportsApi.download(reportId)
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `report_${reportId}.pdf`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success(t('common.success'))
  } catch (error) {
    ElMessage.error(t('common.error'))
  }
}

const fetchReports = async () => {
  loading.value = true
  try {
    // In a real app, this would be a dedicated reports list endpoint
    // For now, we get reports from completed tasks
    const response = await reportsApi.get('latest')
    reports.value = [response.data]
  } catch (error) {
    console.error('Failed to fetch reports', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.report-view {
  padding: 20px;
}
</style>
