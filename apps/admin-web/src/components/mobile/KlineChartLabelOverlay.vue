<script setup lang="ts">
import type { ChartIndicatorLabels } from '@/chart/indicatorLabels'
import { XQ_CHART_LAYOUT } from '@/chart/xueqiuLayout'

defineProps<{
  labels: ChartIndicatorLabels
}>()
</script>

<template>
  <div class="xq-lbl-overlay" aria-hidden="true">
    <div class="xq-lbl-overlay__row xq-lbl-overlay__row--vol">
      <span
        v-for="(part, i) in labels.volume"
        :key="'v' + i"
        class="xq-lbl-overlay__part"
        :style="part.color ? { color: part.color } : undefined"
      >
        {{ part.text }}
      </span>
    </div>
    <div class="xq-lbl-overlay__row xq-lbl-overlay__row--sub2">
      <span
        v-for="(part, i) in labels.sub2"
        :key="'s' + i"
        class="xq-lbl-overlay__part"
        :style="part.color ? { color: part.color } : undefined"
      >
        {{ part.text }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.xq-lbl-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}

.xq-lbl-overlay__row {
  position: absolute;
  left: 8px;
  right: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: calc(100% - 16px);
  padding: 2px 4px;
  font-size: 10px;
  line-height: 1.2;
  color: #666;
  background: rgba(255, 255, 255, 0.82);
  border-radius: 2px;
  text-shadow: 0 0 2px #fff;
}

.xq-lbl-overlay__row--vol {
  top: v-bind('XQ_CHART_LAYOUT.volTop');
}

.xq-lbl-overlay__row--sub2 {
  top: v-bind('XQ_CHART_LAYOUT.ind2Top');
}

.xq-lbl-overlay__part {
  white-space: nowrap;
}
</style>
