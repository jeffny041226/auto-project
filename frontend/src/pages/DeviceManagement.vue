<template>
  <div class="device-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Device Management</span>
          <el-button type="primary" @click="handleCreate">Add Device</el-button>
        </div>
      </template>
      <el-table :data="devices" v-loading="loading" style="width: 100%">
        <el-table-column prop="device_id" label="Device ID" width="150" />
        <el-table-column prop="device_name" label="Device Name" width="150" />
        <el-table-column prop="os_version" label="OS Version" width="100" />
        <el-table-column prop="model" label="Model" />
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_task_id" label="Current Task" width="150">
          <template #default="{ row }">
            {{ row.current_task_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="last_heartbeat" label="Last Heartbeat" width="180">
          <template #default="{ row }">
            {{ row.last_heartbeat ? formatDate(row.last_heartbeat) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="editDevice(row.device_id)">
              Edit
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="50%">
      <el-form :model="form" label-width="120px">
        <el-form-item label="Device ID">
          <el-input v-model="form.device_id" :disabled="isEditing" />
        </el-form-item>
        <el-form-item label="Device Name">
          <el-input v-model="form.device_name" />
        </el-form-item>
        <el-form-item label="OS Version">
          <el-input v-model="form.os_version" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="form.model" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="handleSave">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useDeviceStore } from '@/stores/device'

const deviceStore = useDeviceStore()

const loading = computed(() => deviceStore.loading)
const devices = computed(() => deviceStore.devices)

const dialogVisible = ref(false)
const dialogTitle = ref('')
const isEditing = ref(false)

const form = reactive({
  device_id: '',
  device_name: '',
  os_version: '',
  model: '',
})

const getStatusType = (status: string) => {
  const types: Record<string, any> = {
    online: 'success',
    offline: 'info',
    busy: 'warning',
  }
  return types[status] || 'info'
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const handleCreate = () => {
  Object.assign(form, {
    device_id: '',
    device_name: '',
    os_version: '',
    model: '',
  })
  isEditing.value = false
  dialogTitle.value = 'Add Device'
  dialogVisible.value = true
}

const editDevice = async (deviceId: string) => {
  const device = devices.value.find((d) => d.device_id === deviceId)
  if (device) {
    Object.assign(form, device)
    isEditing.value = true
    dialogTitle.value = 'Edit Device'
    dialogVisible.value = true
  }
}

const handleSave = async () => {
  try {
    if (isEditing.value) {
      await deviceStore.updateDevice(form.device_id, form)
      ElMessage.success('Device updated successfully')
    } else {
      await deviceStore.createDevice(form)
      ElMessage.success('Device added successfully')
    }
    dialogVisible.value = false
    deviceStore.fetchDevices()
  } catch (error) {
    ElMessage.error('Failed to save device')
  }
}

onMounted(() => {
  deviceStore.fetchDevices()
})
</script>

<style scoped>
.device-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
