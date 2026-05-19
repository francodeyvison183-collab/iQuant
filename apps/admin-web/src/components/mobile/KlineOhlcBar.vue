<script setup lang="ts">
import { computed } from 'vue'
import type { OhlcDisplay } from '@/chart/klineOhlc'
import { XQ } from '@/chart/xueqiuTheme'

const props = defineProps<{
  ohlc: OhlcDisplay | null
}>()

const chgColor = computed(() => (props.ohlc?.isUp ? XQ.up : XQ.down))

function fmtChgPct(pct: number): string {
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function fmtChgAbs(abs: number): string {
  const sign = abs >= 0 ? '+' : ''
  return `${sign}${abs.toFixed(2)}`
}
</script>

<template>
  <div v-if="ohlc" class="xq-ohlc" aria-live="polite">
    <span class="xq-ohlc__time">{{ ohlc.time }}</span>
    <span class="xq-ohlc__item">开 <b>{{ ohlc.open }}</b></span>
    <span class="xq-ohlc__item">高 <b :style="{ color: XQ.up }">{{ ohlc.high }}</b></span>
    <span class="xq-ohlc__item">低 <b :style="{ color: XQ.down }">{{ ohlc.low }}</b></span>
    <span class="xq-ohlc__item">收 <b :style="{ color: chgColor }">{{ ohlc.close }}</b></span>
    <span class="xq-ohlc__chg" :style="{ color: chgColor }">
      {{ fmtChgAbs(ohlc.changeAbs) }} {{ fmtChgPct(ohlc.changePct) }}
    </span>
  </div>
</template>

<style scoped>
.xq-ohlc {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  min-height: 28px;
  padding: 4px 8px;
  font-size: 11px;
  color: #666;
  background: #fff;
  border-bottom: 0.5px solid #eee;
  line-height: 1.3;
}

.xq-ohlc__time {
  flex: 0 0 auto;
  color: #333;
  font-weight: 500;
}

.xq-ohlc__item b {
  font-weight: 600;
  color: #333;
}

.xq-ohlc__chg {
  font-weight: 600;
}
</style>
