<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { getCoverage, listSymbols, queryBars, type BarPoint, type SymbolItem } from '@/api/market'

const market = ref<string>('')
const keyword = ref('')
const symbols = ref<SymbolItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loadingSymbols = ref(false)

const selected = ref<SymbolItem | null>(null)
const period = ref('day')
const bars = ref<BarPoint[]>([])
const loadingBars = ref(false)
const coverage = ref<{ first_bar_time: string | null; last_bar_time: string | null; bar_count: number } | null>(null)

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

async function loadSymbols() {
  loadingSymbols.value = true
  try {
    const r = await listSymbols({
      market: market.value || undefined,
      keyword: keyword.value || undefined,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    symbols.value = r.data
    total.value = r.total || 0
  } finally {
    loadingSymbols.value = false
  }
}

async function selectSymbol(row: SymbolItem) {
  selected.value = row
  await loadBars()
}

async function loadBars() {
  if (!selected.value) return
  loadingBars.value = true
  try {
    const [b, c] = await Promise.all([
      queryBars({ full_code: selected.value.full_code, period: period.value, limit: 500 }),
      getCoverage({ full_code: selected.value.full_code, period: period.value }),
    ])
    bars.value = b.data.bars
    coverage.value = c.data
    renderChart()
  } finally {
    loadingBars.value = false
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const dates = bars.value.map((b) => b.bar_time.replace('T', ' ').slice(0, 16))
  const candles = bars.value.map((b) => [
    Number(b.open),
    Number(b.close),
    Number(b.low),
    Number(b.high),
  ])
  const volumes = bars.value.map((b) => b.volume)
  chart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线', '成交量'] },
    grid: [
      { left: 50, right: 20, top: 30, height: '60%' },
      { left: 50, right: 20, top: '76%', height: '18%' },
    ],
    xAxis: [
      { type: 'category', data: dates, scale: true, boundaryGap: false, axisLine: { onZero: false } },
      { type: 'category', gridIndex: 1, data: dates, axisLabel: { show: false }, axisTick: { show: false }, axisLine: { show: false } },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { show: true, xAxisIndex: [0, 1], type: 'slider', top: '95%', start: 60, end: 100 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candles,
        itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#94a3b8' },
      },
    ],
  })
  chart.resize()
}

const previewRows = computed(() => bars.value.slice(-20))

onMounted(loadSymbols)
watch([market, keyword, page, pageSize], loadSymbols)
watch(period, loadBars)
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="9">
      <el-card shadow="never">
        <template #header>标的列表</template>
        <el-form inline>
          <el-form-item label="市场">
            <el-select v-model="market" placeholder="全部" clearable style="width: 120px">
              <el-option label="上海" value="sh" />
              <el-option label="深圳" value="sz" />
              <el-option label="北京" value="bj" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键字">
            <el-input v-model="keyword" placeholder="代码或名称" clearable style="width: 180px" />
          </el-form-item>
        </el-form>
        <el-table v-loading="loadingSymbols" :data="symbols" highlight-current-row @row-click="selectSymbol" stripe size="small">
          <el-table-column prop="full_code" label="代码" width="110" />
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="market" label="市场" width="80" />
        </el-table>
        <el-pagination
          class="mt"
          small
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, prev, pager, next, sizes"
        />
      </el-card>
    </el-col>

    <el-col :span="15">
      <el-card shadow="never">
        <template #header>
          <div class="header">
            <span>
              {{ selected ? `${selected.full_code} ${selected.name}` : '请选择标的' }}
            </span>
            <el-radio-group v-model="period" size="small">
              <el-radio-button value="5m">5分</el-radio-button>
              <el-radio-button value="30m">30分</el-radio-button>
              <el-radio-button value="day">日线</el-radio-button>
              <el-radio-button value="week">周线</el-radio-button>
            </el-radio-group>
          </div>
        </template>

        <el-empty v-if="!selected" description="点击左侧标的查看 K 线" />
        <div v-else v-loading="loadingBars">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="数据起点">{{ coverage?.first_bar_time || '-' }}</el-descriptions-item>
            <el-descriptions-item label="数据终点">{{ coverage?.last_bar_time || '-' }}</el-descriptions-item>
            <el-descriptions-item label="累计 K 线">{{ coverage?.bar_count ?? 0 }}</el-descriptions-item>
          </el-descriptions>

          <div ref="chartRef" class="chart" />

          <el-table :data="previewRows" size="small" stripe class="mt">
            <el-table-column prop="bar_time" label="时间" min-width="160" />
            <el-table-column prop="open" label="开" align="right" />
            <el-table-column prop="high" label="高" align="right" />
            <el-table-column prop="low" label="低" align="right" />
            <el-table-column prop="close" label="收" align="right" />
            <el-table-column prop="volume" label="量" align="right" />
            <el-table-column prop="amount" label="额" align="right" />
          </el-table>
        </div>
      </el-card>
    </el-col>
  </el-row>
</template>

<style scoped>
.header { display: flex; justify-content: space-between; align-items: center; }
.mt { margin-top: 12px; }
.chart { width: 100%; height: 420px; margin-top: 12px; }
</style>
