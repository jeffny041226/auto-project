<template>
  <div class="instruction-input">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Natural Language Test Instruction</span>
        </div>
      </template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="Instruction">
          <el-input
            v-model="form.instruction"
            type="textarea"
            :rows="4"
            placeholder="e.g., Open WeChat and login with account test@example.com"
          />
        </el-form-item>
        <el-form-item label="Device">
          <el-select v-model="form.deviceId" placeholder="Select device (optional)">
            <el-option label="Auto select" value="" />
            <el-option
              v-for="device in devices"
              :key="device.device_id"
              :label="device.device_name"
              :value="device.device_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">
            Generate & Execute
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="parsedResult" style="margin-top: 20px">
      <template #header>
        <span>Parsed Intention</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="Intent">
          <el-tag>{{ parsedResult.intent }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Confidence">
          {{ (parsedResult.confidence * 100).toFixed(1) }}%
        </el-descriptions-item>
        <el-descriptions-item
          v-for="(value, key) in parsedResult.entities"
          :key="key"
          :label="key"
        >
          {{ value }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="generatedScript" style="margin-top: 20px">
      <template #header>
        <span>Generated Script</span>
      </template>
      <el-tabs>
        <el-tab-pane label="Pseudo Code">
          <pre class="code-block">{{ generatedScript.pseudo_code }}</pre>
        </el-tab-pane>
        <el-tab-pane label="Maestro YAML">
          <pre class="code-block">{{ generatedScript.maestro_yaml }}</pre>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-card v-if="taskId" style="margin-top: 20px">
      <template #header>
        <span>Task Created</span>
      </template>
      <div class="task-info">
        <p>Task ID: <strong>{{ taskId }}</strong></p>
        <p>Status: <el-tag :type="taskStatus === 'running' ? 'primary' : 'info'">{{ taskStatus }}</el-tag></p>
        <el-button type="primary" @click="$router.push(`/tasks/${taskId}`)">
          View Task Details
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'
import { useTaskStore } from '@/stores/task'

const router = useRouter()
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

import { computed } from 'vue'

const handleSubmit = async () => {
  if (!form.instruction.trim()) {
    ElMessage.warning('Please enter an instruction')
    return
  }

  submitting.value = true
  try {
    // Create task - backend will handle intention parsing, script generation, and execution
    const task = await taskStore.createTask(form.instruction, form.deviceId || undefined)
    taskId.value = task.task_id
    taskStatus.value = task.status

    ElMessage.success('Task created successfully')

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
    ElMessage.error(error.message || 'Failed to create task')
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
