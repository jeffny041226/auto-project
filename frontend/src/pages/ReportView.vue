<template>
  <div class="report-view">
    <el-card>
      <template #header>
        <span>Test Reports</span>
      </template>
      <el-table :data="reports" v-loading="loading" style="width: 100%">
        <el-table-column prop="report_id" label="Report ID" width="150" />
        <el-table-column prop="task_id" label="Task ID" width="150" />
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'passed' ? 'success' : 'danger'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_steps" label="Total Steps" width="100" />
        <el-table-column prop="passed_steps" label="Passed" width="80" />
        <el-table-column prop="failed_steps" label="Failed" width="80" />
        <el-table-column prop="duration_ms" label="Duration" width="100">
          <template #default="{ row }">
            {{ row.duration_ms ? `${(row.duration_ms / 1000).toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created At" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="viewReport(row.report_id)">
              View
            </el-button>
            <el-button type="success" size="small" link @click="downloadReport(row.report_id)">
              Download
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { reportsApi } from '@/api'

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
    ElMessage.success('Report downloaded successfully')
  } catch (error) {
    ElMessage.error('Failed to download report')
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
