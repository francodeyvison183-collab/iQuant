<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { MAIN_CHART_OPTIONS, SUB_CHART2_OPTIONS, type MainChartKind, type SubChart2Kind } from '@/chart/types'
import { XQ } from '@/chart/xueqiuTheme'

const mainKind = defineModel<MainChartKind>('mainKind', { required: true })
const subChart2 = defineModel<SubChart2Kind>('subChart2', { required: true })

const scrollRef = ref<HTMLDivElement | null>(null)
const tabRefs = ref<Record<string, HTMLButtonElement | null>>({})
const fadeLeft = ref(false)
const fadeRight = ref(false)

function setTabRef(value: string, el: HTMLButtonElement | null) {
  if (el) tabRefs.value[value] = el
}

function updateFade() {
  const el = scrollRef.value
  if (!el) {
    fadeLeft.value = false
    fadeRight.value = false
    return
  }
  const max = el.scrollWidth - el.clientWidth
  fadeLeft.value = el.scrollLeft > 2
  fadeRight.value = max > 2 && el.scrollLeft < max - 2
}

function scrollActiveIntoView() {
  const el = tabRefs.value[subChart2.value]
  el?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
}

watch(subChart2, () => {
  void nextTick(() => {
    scrollActiveIntoView()
    updateFade()
  })
})

onMounted(() => {
  updateFade()
  void nextTick(scrollActiveIntoView)
  scrollRef.value?.addEventListener('scroll', updateFade, { passive: true })
  window.addEventListener('resize', updateFade)
})

onUnmounted(() => {
  scrollRef.value?.removeEventListener('scroll', updateFade)
  window.removeEventListener('resize', updateFade)
})
</script>

<template>
  <div class="xq-ind-bar">
    <button
      v-for="opt in MAIN_CHART_OPTIONS"
      :key="opt.value"
      type="button"
      class="xq-ind-bar__main"
      :class="{ 'xq-ind-bar__main--on': mainKind === opt.value }"
      @click="mainKind = opt.value"
    >
      {{ opt.label }}
    </button>
    <span class="xq-ind-bar__vol">成交量</span>
    <div class="xq-ind-bar__scroll-wrap">
      <div
        v-show="fadeLeft"
        class="xq-ind-bar__fade xq-ind-bar__fade--left"
        aria-hidden="true"
      />
      <div ref="scrollRef" class="xq-ind-bar__scroll">
        <button
          v-for="opt in SUB_CHART2_OPTIONS"
          :key="opt.value"
          :ref="(el) => setTabRef(opt.value, el as HTMLButtonElement | null)"
          type="button"
          class="xq-ind-bar__tab"
          :class="{ 'xq-ind-bar__tab--on': subChart2 === opt.value }"
          @click="subChart2 = opt.value"
        >
          {{ opt.label }}
        </button>
      </div>
      <div
        v-show="fadeRight"
        class="xq-ind-bar__fade xq-ind-bar__fade--right"
        aria-hidden="true"
      />
    </div>
  </div>
</template>

<style scoped>
.xq-ind-bar {
  display: flex;
  align-items: stretch;
  flex-shrink: 0;
  height: 32px;
  background: #fff;
  border-top: 0.5px solid #eee;
}

.xq-ind-bar__main {
  flex: 0 0 auto;
  padding: 0 12px;
  border: none;
  border-right: 0.5px solid #eee;
  background: transparent;
  font-size: 13px;
  color: #666;
  touch-action: manipulation;
}

.xq-ind-bar__main--on {
  color: v-bind('XQ.up');
  font-weight: 600;
}

.xq-ind-bar__vol {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  padding: 0 12px;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  background: #fff;
  border-right: 0.5px solid #eee;
  z-index: 2;
}

.xq-ind-bar__scroll-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.xq-ind-bar__scroll {
  display: flex;
  align-items: center;
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  scroll-behavior: smooth;
}

.xq-ind-bar__scroll::-webkit-scrollbar {
  display: none;
}

.xq-ind-bar__tab {
  flex: 0 0 auto;
  position: relative;
  padding: 0 14px;
  height: 100%;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #666;
  white-space: nowrap;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.xq-ind-bar__tab::after {
  content: '';
  position: absolute;
  right: 0;
  top: 8px;
  bottom: 8px;
  width: 0.5px;
  background: #eee;
}

.xq-ind-bar__tab:last-child::after {
  display: none;
}

.xq-ind-bar__tab--on {
  color: v-bind('XQ.up');
  font-weight: 600;
}

.xq-ind-bar__fade {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 20px;
  pointer-events: none;
  z-index: 1;
}

.xq-ind-bar__fade--left {
  left: 0;
  background: linear-gradient(to right, #fff 30%, rgba(255, 255, 255, 0));
}

.xq-ind-bar__fade--right {
  right: 0;
  background: linear-gradient(to left, #fff 30%, rgba(255, 255, 255, 0));
}
</style>
