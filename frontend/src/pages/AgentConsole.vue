<template>
  <div class="agent-console">
    <el-row :gutter="20">
      <!-- Left Panel: Task Control -->
      <el-col :span="12">
        <el-card class="task-control-card">
          <template #header>
            <div class="card-header">
              <span>{{ t('agent.console') }}</span>
              <el-tag :type="connectionStatusType" size="small">{{ connectionStatusText }}</el-tag>
            </div>
          </template>

          <el-form :model="form" label-width="120px">
            <el-form-item :label="t('agent.instruction')">
              <el-input
                v-model="form.instruction"
                type="textarea"
                :rows="4"
                :placeholder="t('agent.instructionPlaceholder')"
                :disabled="isTaskRunning"
              />
            </el-form-item>

            <el-form-item :label="t('agent.device')">
              <el-select
                v-model="form.deviceSerial"
                :placeholder="t('agent.selectDevice')"
                :disabled="isTaskRunning"
              >
                <el-option :label="t('agent.autoSelect')" value="" />
                <el-option
                  v-for="device in devices"
                  :key="device.device_id"
                  :value="device.device_id"
                >
                  <span>{{ device.device_name || device.device_id }}</span>
                  <el-tag size="small" :type="getDeviceStatusType(device.status)" style="margin-left: 8px">
                    {{ t(`status.${device.status}`) }}
                  </el-tag>
                </el-option>
              </el-select>
            </el-form-item>

            <el-form-item :label="t('task.instruction')">
              <el-input-number v-model="form.maxSteps" :min="1" :max="500" :disabled="isTaskRunning" />
            </el-form-item>

            <el-form-item>
              <el-button
                v-if="!isTaskRunning"
                type="primary"
                :loading="starting"
                @click="handleStartTask"
              >
                {{ t('agent.startTask') }}
              </el-button>
              <el-button
                v-else
                type="danger"
                @click="handleStopTask"
              >
                {{ t('agent.stopTask') }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- Task Status Card -->
        <el-card v-if="currentTask" class="task-status-card" style="margin-top: 20px">
          <template #header>
            <span>{{ t('agent.status') }}</span>
          </template>

          <el-descriptions :column="2" border>
            <el-descriptions-item :label="t('agent.taskId')">
              <el-tag size="small">{{ currentTask.task_id }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('agent.status')">
              <el-tag :type="taskStatusType">{{ t(`status.${currentTask.status}`) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('agent.progress')">
              <el-progress :percentage="currentTask.progress" :status="progressStatus" />
            </el-descriptions-item>
            <el-descriptions-item :label="t('agent.currentStep')">
              {{ currentTask.current_step }} / {{ currentTask.max_steps }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('agent.message')" :span="2">
              {{ currentTask.message || '-' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="currentTask.error" :label="t('agent.error')" :span="2">
              <el-alert type="error" :closable="false">{{ currentTask.error }}</el-alert>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- Right Panel: Script Output -->
      <el-col :span="12">
        <el-card class="script-output-card">
          <template #header>
            <div class="card-header">
              <span>{{ t('agent.generatedScript') }}</span>
              <el-button
                v-if="generatedScript"
                type="primary"
                size="small"
                @click="handleSaveScript"
              >
                {{ t('agent.saveScript') }}
              </el-button>
            </div>
          </template>

          <div v-if="generatedScript" class="script-container">
            <el-tabs>
              <el-tab-pane :label="t('task.maestroYaml')">
                <el-input
                  v-model="editableScript"
                  type="textarea"
                  :rows="20"
                  class="script-editor"
                />
              </el-tab-pane>
            </el-tabs>
          </div>
          <el-empty v-else :description="t('agent.noScriptYet')" />
        </el-card>

        <!-- Script History -->
        <el-card class="script-history-card" style="margin-top: 20px">
          <template #header>
            <span>{{ t('agent.scriptHistory') }}</span>
          </template>

          <el-table :data="taskHistory" style="width: 100%" max-height="300">
            <el-table-column :label="t('agent.taskId')" prop="task_id" width="180">
              <template #default="{ row }">
                <el-tag size="small">{{ row.task_id.substring(0, 8) }}...</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('agent.status')" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ t(`status.${row.status}`) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('task.instruction')" prop="message">
              <template #default="{ row }">
                {{ row.message || '-' }}
              </template>
            </el-table-column>
            <el-table-column :label="t('task.actions')" width="120">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'completed' && row.generated_script"
                  type="primary"
                  size="small"
                  @click="handleViewScript(row)"
                >
                  {{ t('agent.viewScript') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Script Save Dialog -->
    <el-dialog v-model="saveDialogVisible" :title="t('agent.saveScript')" width="500px">
      <el-form :model="saveForm" label-width="100px">
        <el-form-item :label="t('script.name')">
          <el-input v-model="saveForm.name" placeholder="My Test Script" />
        </el-form-item>
        <el-form-item :label="t('task.intent')">
          <el-input v-model="saveForm.intent" placeholder="Open WeChat and login" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="confirmSaveScript">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import { agentApi } from '@/api'

const { t } = useI18n()
const deviceStore = useDeviceStore()

// Form state
const form = reactive({
  instruction: '',
  deviceSerial: '',
  maxSteps: 100,
})

// Task state
const starting = ref(false)
const isTaskRunning = ref(false)
const currentTask = ref<any>(null)
const generatedScript = ref('')
const editableScript = ref('')
const taskHistory = ref<any[]>([])

// WebSocket
let ws: WebSocket | null = null
const wsConnected = ref(false)

// Save dialog
const saveDialogVisible = ref(false)
const saveForm = reactive({
  name: '',
  intent: '',
})

// Computed
const devices = computed(() => deviceStore.devices)

const connectionStatusType = computed(() => {
  if (wsConnected.value) return 'success'
  if (isTaskRunning.value) return 'warning'
  return 'info'
})

const connectionStatusText = computed(() => {
  if (wsConnected.value) return t('agent.connected')
  if (isTaskRunning.value) return t('agent.connecting')
  return t('agent.disconnected')
})

const taskStatusType = computed(() => {
  if (!currentTask.value) return 'info'
  switch (currentTask.value.status) {
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'warning'
    default: return 'info'
  }
})

const progressStatus = computed(() => {
  if (!currentTask.value) return undefined
  if (currentTask.value.status === 'failed') return 'exception'
  if (currentTask.value.status === 'completed') return 'success'
  return undefined
})

// Methods
const getDeviceStatusType = (status: string) => {
  const types: Record<string, string> = {
    online: 'success',
    offline: 'info',
    busy: 'warning',
  }
  return types[status] || 'info'
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'running': return 'primary'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'warning'
    default: return 'info'
  }
}

const handleStartTask = async () => {
  if (!form.instruction.trim()) {
    ElMessage.warning(t('task.pleaseEnterInstruction'))
    return
  }

  starting.value = true
  try {
    const response = await agentApi.createTask({
      instruction: form.instruction,
      device_serial: form.deviceSerial || 'auto',
      max_steps: form.maxSteps,
    })

    const taskId = response.data.task_id
    currentTask.value = {
      task_id: taskId,
      status: 'starting',
      progress: 0,
      current_step: 0,
      max_steps: form.maxSteps,
      message: '',
    }

    isTaskRunning.value = true
    connectWebSocket(taskId)
    ElMessage.success(t('agent.taskCompleted') + ': ' + taskId)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || t('task.failedToCreateTask'))
  } finally {
    starting.value = false
  }
}

const handleStopTask = async () => {
  if (!currentTask.value?.task_id) return

  try {
    await agentApi.stopTask(currentTask.value.task_id)
    ElMessage.success(t('agent.cancelled'))
  } catch (error: any) {
    ElMessage.error(error.message || 'Failed to stop task')
  }
}

const connectWebSocket = (taskId: string) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/v1/agent/ws/${taskId}`

  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    wsConnected.value = true
    console.log('WebSocket connected')
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleWsMessage(data)
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e)
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    ElMessage.error(t('agent.wsError'))
  }

  ws.onclose = () => {
    wsConnected.value = false
    console.log('WebSocket closed')
  }
}

const handleWsMessage = (data: any) => {
  switch (data.type) {
    case 'status':
      currentTask.value = {
        ...currentTask.value,
        status: data.status,
        progress: data.progress,
        current_step: data.current_step,
        max_steps: data.max_steps,
        message: data.message,
        error: data.error,
      }

      if (data.status === 'completed') {
        isTaskRunning.value = false
        ElMessage.success(t('agent.taskCompleted'))
      } else if (data.status === 'failed') {
        isTaskRunning.value = false
        ElMessage.error(t('agent.taskFailed') + ': ' + data.error)
      }
      break

    case 'script':
      generatedScript.value = data.script
      editableScript.value = data.script
      break

    case 'error':
      ElMessage.error(data.message)
      break

    case 'stopped':
      isTaskRunning.value = false
      break
  }
}

const handleViewScript = (task: any) => {
  if (task.generated_script) {
    generatedScript.value = task.generated_script
    editableScript.value = task.generated_script
  }
}

const handleSaveScript = () => {
  saveForm.name = ''
  saveForm.intent = form.instruction
  saveDialogVisible.value = true
}

const confirmSaveScript = async () => {
  if (!saveForm.name.trim()) {
    ElMessage.warning('Please enter script name')
    return
  }

  try {
    await agentApi.getScript(currentTask.value.task_id)
    // The script is already in editableScript, save it as a new script
    ElMessage.success('Script saved (mock - API endpoint needed)')
    saveDialogVisible.value = false
  } catch (error) {
    ElMessage.error('Failed to save script')
  }
}

const fetchTaskHistory = async () => {
  try {
    const response = await agentApi.listTasks()
    taskHistory.value = response.data.tasks || []
  } catch (error) {
    console.error('Failed to fetch task history:', error)
  }
}

const disconnectWebSocket = () => {
  if (ws) {
    ws.close()
    ws = null
  }
}

// Lifecycle
onMounted(() => {
  deviceStore.fetchDevices()
  fetchTaskHistory()
})

onUnmounted(() => {
  disconnectWebSocket()
})
</script>

<style scoped>
.agent-console {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-control-card,
.script-output-card,
.script-history-card {
  height: 100%;
}

.script-container {
  min-height: 400px;
}

.script-editor {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.script-editor :deep(.el-textarea__inner) {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
}
</style>
