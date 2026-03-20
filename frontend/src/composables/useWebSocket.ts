"use WebSocket composable for real-time updates."
import { ref, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'

interface WebSocketMessage {
  type: string
  [key: string]: any
}

export function useWebSocket() {
  const userStore = useUserStore()
  const connected = ref(false)
  const messages = ref<WebSocketMessage[]>([])
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null
  let pingInterval: number | null = null

  const connect = () => {
    const token = localStorage.getItem('token')
    if (!token) {
      error.value = 'No token available'
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`

    try {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        connected.value = true
        error.value = null
        console.log('WebSocket connected')

        // Start ping interval
        pingInterval = window.setInterval(() => {
          send({ type: 'ping' })
        }, 30000)
      }

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          messages.value.push(message)

          // Handle different message types
          switch (message.type) {
            case 'task_update':
              handleTaskUpdate(message)
              break
            case 'task_completed':
              handleTaskCompleted(message)
              break
            case 'connected':
              console.log('WebSocket authenticated')
              break
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message', e)
        }
      }

      ws.onerror = (e) => {
        console.error('WebSocket error', e)
        error.value = 'Connection error'
      }

      ws.onclose = () => {
        connected.value = false
        console.log('WebSocket disconnected')

        // Cleanup ping interval
        if (pingInterval) {
          clearInterval(pingInterval)
          pingInterval = null
        }

        // Attempt reconnect
        if (userStore.isLoggedIn) {
          reconnectTimer = window.setTimeout(() => {
            console.log('Attempting WebSocket reconnect...')
            connect()
          }, 3000)
        }
      }
    } catch (e) {
      error.value = 'Failed to connect'
      console.error('WebSocket connection failed', e)
    }
  }

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    if (pingInterval) {
      clearInterval(pingInterval)
      pingInterval = null
    }

    if (ws) {
      ws.close()
      ws = null
    }

    connected.value = false
  }

  const send = (data: object) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
    }
  }

  const subscribeToTask = (taskId: string) => {
    send({ type: 'subscribe', task_id: taskId })
  }

  const unsubscribeFromTask = (taskId: string) => {
    send({ type: 'unsubscribe', task_id: taskId })
  }

  const handleTaskUpdate = (message: WebSocketMessage) => {
    console.log('Task update received:', message)
    // Can emit event or update store
  }

  const handleTaskCompleted = (message: WebSocketMessage) => {
    console.log('Task completed:', message)
    // Can show notification
  }

  onMounted(() => {
    if (userStore.isLoggedIn) {
      connect()
    }
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    messages,
    error,
    connect,
    disconnect,
    send,
    subscribeToTask,
    unsubscribeFromTask,
  }
}
