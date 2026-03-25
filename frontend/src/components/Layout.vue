<template>
  <div class="layout">
    <el-container>
      <el-header>
        <div class="header-content">
          <h2>{{ t('header.title') }}</h2>
          <div class="user-info">
            <el-select v-model="currentLocale" size="small" style="width: 100px" @change="handleLocaleChange">
              <el-option label="English" value="en" />
              <el-option label="中文" value="zh" />
            </el-select>
            <span>{{ username }}</span>
            <el-button type="danger" size="small" @click="handleLogout">{{ t('menu.logout') }}</el-button>
          </div>
        </div>
      </el-header>
      <el-container>
        <el-aside width="200px">
          <el-menu :default-active="activeMenu" router>
            <el-menu-item index="/">
              <el-icon><HomeFilled /></el-icon>
              <span>{{ t('menu.dashboard') }}</span>
            </el-menu-item>
            <el-menu-item index="/instruction">
              <el-icon><Edit /></el-icon>
              <span>{{ t('menu.instruction') }}</span>
            </el-menu-item>
            <el-menu-item index="/agent">
              <el-icon><Connection /></el-icon>
              <span>{{ t('agent.title') }}</span>
            </el-menu-item>
            <el-menu-item index="/scripts">
              <el-icon><Document /></el-icon>
              <span>{{ t('menu.scripts') }}</span>
            </el-menu-item>
            <el-menu-item index="/tasks">
              <el-icon><List /></el-icon>
              <span>{{ t('menu.tasks') }}</span>
            </el-menu-item>
            <el-menu-item index="/devices">
              <el-icon><Monitor /></el-icon>
              <span>{{ t('menu.devices') }}</span>
            </el-menu-item>
            <el-menu-item index="/reports">
              <el-icon><DataAnalysis /></el-icon>
              <span>{{ t('menu.reports') }}</span>
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/stores/user'
import { HomeFilled, Edit, Document, List, Monitor, DataAnalysis, Connection } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { t, locale } = useI18n()

const currentLocale = ref(locale.value)

const username = computed(() => userStore.username)
const activeMenu = computed(() => route.path)

const handleLocaleChange = (value: string) => {
  locale.value = value
  localStorage.setItem('locale', value)
}

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  height: 100vh;
}

.el-container {
  height: 100%;
}

.el-header {
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
  font-size: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.el-aside {
  background: #f5f7fa;
}

.el-main {
  background: #f0f2f5;
  padding: 20px;
}
</style>
