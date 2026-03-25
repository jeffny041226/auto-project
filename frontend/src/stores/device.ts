import { defineStore } from 'pinia'
import { devicesApi } from '@/api'

interface Device {
  device_id: string
  device_name: string
  os_version: string
  model: string
  status: string
  current_task_id?: string
  last_heartbeat?: string
}

interface DeviceState {
  devices: Device[]
  total: number
  loading: boolean
}

export const useDeviceStore = defineStore('device', {
  state: (): DeviceState => ({
    devices: [],
    total: 0,
    loading: false,
  }),

  getters: {
    onlineDevices: (state) => state.devices.filter((d) => d.status === 'online'),
    offlineDevices: (state) => state.devices.filter((d) => d.status === 'offline'),
    busyDevices: (state) => state.devices.filter((d) => d.status === 'busy'),
  },

  actions: {
    async fetchDevices(skip = 0, limit = 20) {
      this.loading = true
      try {
        const response = await devicesApi.list(skip, limit)
        this.devices = response.data.items
        this.total = response.data.total
      } finally {
        this.loading = false
      }
    },

    async createDevice(data: Partial<Device>) {
      const response = await devicesApi.create(data)
      const device = response.data
      this.devices.push(device)
      return device
    },

    async updateDevice(deviceId: string, data: Partial<Device>) {
      const response = await devicesApi.update(deviceId, data)
      const device = response.data
      const index = this.devices.findIndex((d) => d.device_id === deviceId)
      if (index !== -1) {
        this.devices[index] = device
      }
      return device
    },

    updateDeviceStatus(deviceId: string, newStatus: string) {
      const device = this.devices.find((d) => d.device_id === deviceId)
      if (device) {
        device.status = newStatus
        device.last_heartbeat = new Date().toISOString()
      }
    },
  },
})
