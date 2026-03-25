<template>
  <div class="script-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ t('script.list') }}</span>
          <el-button type="primary" @click="handleCreate">{{ t('common.edit') }}</el-button>
        </div>
      </template>
      <el-table :data="scripts" v-loading="loading" style="width: 100%">
        <el-table-column prop="script_id" :label="t('task.taskId')" width="150" />
        <el-table-column prop="intent" :label="t('script.intent')" width="120" />
        <el-table-column prop="version" label="Version" width="80" />
        <el-table-column prop="hit_count" label="Hit Count" width="100" />
        <el-table-column prop="status" :label="t('script.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ t(`status.${row.status}`) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('script.createdAt')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('script.actions')" width="200">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="viewScript(row.script_id)">
              {{ t('task.view') }}
            </el-button>
            <el-button type="primary" size="small" link @click="editScript(row.script_id)">
              {{ t('common.edit') }}
            </el-button>
            <el-button type="danger" size="small" link @click="deleteScript(row.script_id)">
              {{ t('common.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 20px"
        @current-change="handlePageChange"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="70%">
      <el-form v-if="currentScript" :model="currentScript" label-width="120px">
        <el-form-item :label="t('task.taskId')">
          <el-input v-model="currentScript.script_id" disabled />
        </el-form-item>
        <el-form-item :label="t('script.intent')">
          <el-input v-model="currentScript.intent" />
        </el-form-item>
        <el-form-item :label="t('task.pseudoCode')">
          <el-input v-model="currentScript.pseudo_code" type="textarea" :rows="10" />
        </el-form-item>
        <el-form-item :label="t('task.maestroYaml')">
          <el-input v-model="currentScript.maestro_yaml" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSave">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useScriptStore } from '@/stores/script'

const { t } = useI18n()
const scriptStore = useScriptStore()

const currentPage = ref(1)
const pageSize = ref(20)
const dialogVisible = ref(false)
const dialogTitle = ref('')

const scripts = computed(() => scriptStore.scripts)
const loading = computed(() => scriptStore.loading)
const total = computed(() => scriptStore.total)
const currentScript = computed(() => scriptStore.currentScript)

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString()
}

const handleCreate = () => {
  dialogTitle.value = t('common.edit')
  dialogVisible.value = true
}

const viewScript = async (scriptId: string) => {
  await scriptStore.fetchScript(scriptId)
  dialogTitle.value = t('task.view')
  dialogVisible.value = true
}

const editScript = async (scriptId: string) => {
  await scriptStore.fetchScript(scriptId)
  dialogTitle.value = t('common.edit')
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!currentScript.value) return
  try {
    await scriptStore.updateScript(currentScript.value.script_id, currentScript.value)
    ElMessage.success(t('common.success'))
    dialogVisible.value = false
    scriptStore.fetchScripts()
  } catch (error) {
    ElMessage.error(t('common.error'))
  }
}

const deleteScript = async (scriptId: string) => {
  try {
    await ElMessageBox.confirm(t('common.warning'), t('common.warning'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })
    await scriptStore.deleteScript(scriptId)
    ElMessage.success(t('common.success'))
  } catch {
    // Cancelled
  }
}

const handlePageChange = (page: number) => {
  scriptStore.fetchScripts((page - 1) * pageSize.value, pageSize.value)
}

onMounted(() => {
  scriptStore.fetchScripts()
})
</script>

<style scoped>
.script-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
