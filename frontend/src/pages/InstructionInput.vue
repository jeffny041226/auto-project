<template>
  <div class="instruction-input">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ t('instruction.title') }}</span>
        </div>
      </template>
      <el-form :model="form" label-width="120px">
        <el-form-item :label="t('task.instruction')">
          <el-input
            v-model="form.instruction"
            type="textarea"
            :rows="4"
            :placeholder="t('instruction.placeholder')"
          />
        </el-form-item>
        <el-form-item :label="t('task.device')">
          <el-select v-model="form.deviceId" :placeholder="t('task.selectDevice')">
            <el-option :label="t('task.autoSelect')" value="" />
            <el-option
              v-for="device in devices"
              :key="device.device_id"
              :value="device.device_id"
            >
              <span>{{ device.device_name }}</span>
              <el-tag size="small" :type="getDeviceStatusType(device.status)" style="margin-left: 8px">
                {{ t(`status.${device.status}`) }}
              </el-tag>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            {{ t('task.generateExecute') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="parsedResult" style="margin-top: 20px">
      <template #header>
        <span>{{ t('task.parsedIntention') }}</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item :label="t('task.intent')">
          <el-tag>{{ parsedResult.intent }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="t('task.confidence')">
          {{ (parsedResult.confidence * 100).toFixed(1) }}%
        </el-descriptions-item>
        <el-descriptions-item
          v-for="(value, key) in parsedResult.entities"
          :key="key"
          :label="String(key)"
        >
          {{ value }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="generatedScript" style="margin-top: 20px">
      <template #header>
        <span>{{ t('task.generatedScript') }}</span>
      </template>
      <el-tabs>
        <el-tab-pane :label="t('task.pseudoCode')">
          <pre class="code-block">{{ generatedScript.pseudo_code }}</pre>
        </el-tab-pane>
        <el-tab-pane :label="t('task.maestroYaml')">
          <pre class="code-block">{{ generatedScript.maestro_yaml }}</pre>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card v-if="taskId" style="margin-top: 20px">
      <template #header>
        <span>{{ t('task.taskCreated') }}</span>
      </template>
      <div class="task-info">
        <p>{{ t('task.taskId') }}: <strong>{{ taskId }}</strong></p>
        <p>{{ t('task.status') }}: <el-tag :type="taskStatus === 'running' ? 'primary' : 'info'">{{ t(`status.${taskStatus}`) }}</el-tag></p>
        <el-button type="primary" @click="$router.push(`/tasks/${taskId}`)">
          {{ t('task.view') }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import { useTaskStore } from '@/stores/task'

const { t } = useI18n()
const deviceStore = useDeviceStore()
const taskStore = useTaskStore()

const form = reactive({
  instruction: '',
  deviceId: '',
})

const submitting = ref(false)
const parsedResult = ref<any>(null)
const generatedScript = ref<any>(null)
const taskId = ref('')
const taskStatus = ref('')

const devices = computed(() => deviceStore.devices)

const getDeviceStatusType = (status: string) => {
  const types: Record<string, any> = {
    online: 'success',
    offline: 'info',
    busy: 'warning',
  }
  return types[status] || 'info'
}

const handleSubmit = async () => {
  if (!form.instruction.trim()) {
    ElMessage.warning(t('task.pleaseEnterInstruction'))
    return
  }

  submitting.value = true
  try {
    // Create task - backend will handle intention parsing, script generation, and execution
    const task = await taskStore.createTask(form.instruction, form.deviceId || undefined)
    taskId.value = task.task_id
    taskStatus.value = task.status

    ElMessage.success(t('task.taskCreatedSuccess'))

    // In a real implementation, we would poll or use WebSocket to get the parsed result
    // For now, simulate getting parsed intention
    parsedResult.value = {
      intent: 'app_open',
      confidence: 0.95,
      entities: {
        app_name: 'WeChat',
        action: 'login',
      },
    }
  } catch (error: any) {
    ElMessage.error(error.message || t('task.failedToCreateTask'))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  deviceStore.fetchDevices()
})
</script>

<style scoped>
.instruction-input {
  padding: 20px;
}

.card-header {
  font-size: 18px;
  font-weight: bold;
}

.code-block {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 5px;
  overflow-x: auto;
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.task-info {
  text-align: center;
  padding: 20px;
}

.task-info p {
  margin: 10px 0;
}
</style>
