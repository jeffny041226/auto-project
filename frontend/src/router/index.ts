import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '/',
        name: 'Dashboard',
        component: () => import('@/pages/Dashboard.vue'),
      },
      {
        path: '/instruction',
        name: 'InstructionInput',
        component: () => import('@/pages/InstructionInput.vue'),
      },
      {
        path: '/agent',
        name: 'AgentConsole',
        component: () => import('@/pages/AgentConsole.vue'),
      },
      {
        path: '/scripts',
        name: 'ScriptManagement',
        component: () => import('@/pages/ScriptManagement.vue'),
      },
      {
        path: '/tasks',
        name: 'TaskList',
        component: () => import('@/pages/TaskList.vue'),
      },
      {
        path: '/tasks/:id',
        name: 'TaskDetail',
        component: () => import('@/pages/TaskDetail.vue'),
      },
      {
        path: '/devices',
        name: 'DeviceManagement',
        component: () => import('@/pages/DeviceManagement.vue'),
      },
      {
        path: '/reports',
        name: 'ReportView',
        component: () => import('@/pages/ReportView.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth !== false)

  if (requiresAuth && !userStore.token) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && userStore.token) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

export default router
