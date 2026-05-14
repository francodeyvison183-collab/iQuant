<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { onlineFetch } from '@/api/market'

const form = ref({ full_code: 'sh600519', period: 'day', max_count: 800 })
const submitting = ref(false)
const lastInserted = ref<number | null>(null)

async function onFetch() {
  submitting.value = true
  try {
    const r = await onlineFetch(form.value)
    lastInserted.value = r.data.inserted
    ElMessage.success(`已写入 ${r.data.inserted} 根`)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-card shadow="never">
    <el-alert
      title="在线补数说明"
      type="info"
      :closable="false"
      description="使用通达信在线协议直接拉取最近的 K 线并写入数据库。适合：单标的快速补齐当日或最近若干根 K 线。大规模历史导入请使用「历史数据导入」走本地 vipdoc 文件。"
      show-icon
    />

    <el-form class="mt" inline>
      <el-form-item label="完整代码">
        <el-input v-model="form.full_code" placeholder="如 sh600519" style="width: 200px" />
      </el-form-item>
      <el-form-item label="周期">
        <el-select v-model="form.period" style="width: 140px">
          <el-option label="1 分钟" value="1m" />
          <el-option label="5 分钟" value="5m" />
          <el-option label="15 分钟" value="15m" />
          <el-option label="30 分钟" value="30m" />
          <el-option label="60 分钟" value="60m" />
          <el-option label="日线" value="day" />
          <el-option label="周线" value="week" />
          <el-option label="月线" value="month" />
        </el-select>
      </el-form-item>
      <el-form-item label="最多条数">
        <el-input-number v-model="form.max_count" :min="1" :max="8000" :step="100" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="submitting" @click="onFetch">拉取并入库</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="lastInserted !== null"
      class="mt"
      :title="`本次写入 ${lastInserted} 根 K 线（已存在的会自动跳过）`"
      type="success"
      :closable="false"
    />
  </el-card>
</template>

<style scoped>
.mt { margin-top: 16px; }
</style>
