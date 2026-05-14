<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createImportTask, scanPreview, type ScanPreview } from '@/api/market'

const router = useRouter()

const vipdocDir = ref('')
const preview = ref<ScanPreview | null>(null)
const loadingPreview = ref(false)
const submitting = ref(false)
const taskType = ref<'incremental' | 'full'>('incremental')

async function onPreview() {
  loadingPreview.value = true
  try {
    const r = await scanPreview(vipdocDir.value || undefined)
    preview.value = r.data
    if (!preview.value.total_files) {
      ElMessage.warning('未扫描到任何文件，请检查路径或映射')
    }
  } finally {
    loadingPreview.value = false
  }
}

async function onSubmit() {
  submitting.value = true
  try {
    const r = await createImportTask({
      task_type: taskType.value,
      vipdoc_dir: vipdocDir.value || undefined,
    })
    ElMessage.success(`任务已创建: ${r.data.task_id}`)
    router.push({ name: 'market-tasks', query: { task_id: r.data.task_id } })
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  onPreview()
})
</script>

<template>
  <el-card shadow="never">
    <el-form inline>
      <el-form-item label="vipdoc 目录">
        <el-input
          v-model="vipdocDir"
          placeholder="留空使用环境变量 IQUANT_TDX_VIPDOC_DIR"
          style="width: 360px"
        />
      </el-form-item>
      <el-form-item>
        <el-button :loading="loadingPreview" @click="onPreview">扫描预览</el-button>
      </el-form-item>
      <el-form-item label="任务类型">
        <el-radio-group v-model="taskType">
          <el-radio-button value="incremental">增量更新</el-radio-button>
          <el-radio-button value="full">全量重导</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!preview || !preview.total_files"
          @click="onSubmit"
        >
          提交导入任务
        </el-button>
      </el-form-item>
    </el-form>

    <el-divider />

    <el-empty v-if="!preview" description="点击「扫描预览」开始" />

    <div v-else>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="数据目录">{{ preview.data_dir }}</el-descriptions-item>
        <el-descriptions-item label="文件总数">{{ preview.total_files }}</el-descriptions-item>
        <el-descriptions-item label="变更文件（需导入）">
          <el-tag type="warning">{{ preview.changed_files }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="未变文件">
          <el-tag type="info">{{ preview.unchanged_files }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <el-row :gutter="16" class="mt">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>按周期</template>
            <el-table :data="periodRows(preview)" size="small">
              <el-table-column prop="period" label="周期" />
              <el-table-column prop="count" label="文件数" align="right" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>按市场</template>
            <el-table :data="marketRows(preview)" size="small">
              <el-table-column prop="market" label="市场" />
              <el-table-column prop="day" label=".day" align="right" />
              <el-table-column prop="m5" label=".lc5" align="right" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </el-card>
</template>

<script lang="ts">
function periodRows(p: ScanPreview) {
  return Object.entries(p.by_period).map(([period, count]) => ({ period, count }))
}
function marketRows(p: ScanPreview) {
  return Object.entries(p.by_market).map(([market, d]) => ({
    market,
    day: d.day || 0,
    m5: d['5m'] || d['lc5'] || 0,
  }))
}
export { periodRows, marketRows }
</script>

<style scoped>
.mt { margin-top: 16px; }
</style>
