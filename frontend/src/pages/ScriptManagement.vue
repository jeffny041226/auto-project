<template>
  <div class="script-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Script Management</span>
          <el-button type="primary" @click="handleCreate">Create Script</el-button>
        </div>
      </template>
      <el-table :data="scripts" v-loading="loading" style="width: 100%">
        <el-table-column prop="script_id" label="Script ID" width="150" />
        <el-table-column prop="intent" label="Intent" width="120" />
        <el-table-column prop="version" label="Version" width="80" />
        <el-table-column prop="hit_count" label="Hit Count" width="100" />
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="Created At" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="200">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="viewScript(row.script_id)">
              View
            </el-button>
            <el-button type="primary" size="small" link @click="editScript(row.script_id)">
              Edit
            </el-button>
            <el-button type="danger" size="small" link @click="deleteScript(row.script_id)">
              Delete
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
        <el-form-item label="Script ID">
          <el-input v-model="currentScript.script_id" disabled />
        </el-form-item>
        <el-form-item label="Intent">
          <el-input v-model="currentScript.intent" />
        </el-form-item>
        <el-form-item label="Pseudo Code">
          <el-input v-model="currentScript.pseudo_code" type="textarea" :rows="10" />
        </el-form-item>
        <el-form-item label="Maestro YAML">
          <el-input v-model="currentScript.maestro_yaml" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">Close</el-button>
        <el-button type="primary" @click="handleSave">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useScriptStore } from '@/stores/script'

const router = useRouter()
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
  dialogTitle.value = 'Create Script'
  dialogVisible.value = true
}

const viewScript = async (scriptId: string) => {
  await scriptStore.fetchScript(scriptId)
  dialogTitle.value = 'View Script'
  dialogVisible.value = true
}

const editScript = async (scriptId: string) => {
  await scriptStore.fetchScript(scriptId)
  dialogTitle.value = 'Edit Script'
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!currentScript.value) return
  try {
    await scriptStore.updateScript(currentScript.value.script_id, currentScript.value)
    ElMessage.success('Script saved successfully')
    dialogVisible.value = false
    scriptStore.fetchScripts()
  } catch (error) {
    ElMessage.error('Failed to save script')
  }
}

const deleteScript = async (scriptId: string) => {
  try {
    await ElMessageBox.confirm('Are you sure to delete this script?', 'Warning', {
      confirmButtonText: 'OK',
      cancelButtonText: 'Cancel',
      type: 'warning',
    })
    await scriptStore.deleteScript(scriptId)
    ElMessage.success('Script deleted successfully')
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
