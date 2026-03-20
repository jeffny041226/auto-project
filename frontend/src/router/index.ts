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
    name: 'Dashboard',
    component: () => import('@/pages/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/instruction',
    name: 'InstructionInput',
    component: () => import('@/pages/InstructionInput.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/scripts',
    name: 'ScriptManagement',
    component: () => import('@/pages/ScriptManagement.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tasks',
    name: 'TaskList',
    component: () => import('@/pages/TaskList.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/tasks/:id',
    name: 'TaskDetail',
    component: () => import('@/pages/TaskDetail.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/devices',
    name: 'DeviceManagement',
    component: () => import('@/pages/DeviceManagement.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/reports',
    name: 'ReportView',
    component: () => import('@/pages/ReportView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !userStore.token) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && userStore.token) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

export default router
