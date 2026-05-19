<script setup lang="ts">
import { ref } from 'vue'
import KlineChartToolbar from '@/components/mobile/KlineChartToolbar.vue'
import { XQ_CHART_LAYOUT } from '@/chart/xueqiuLayout'
import { XQ } from '@/chart/xueqiuTheme'

defineProps<{
  fullscreen?: boolean
}>()

const emit = defineEmits<{
  reset: []
  zoomIn: []
  zoomOut: []
  panLeft: []
  panRight: []
  toggleFullscreen: []
}>()

const open = ref(false)

function toggle() {
  open.value = !open.value
}
</script>

<template>
  <div
    class="xq-tools-flyout"
    :class="{ 'xq-tools-flyout--open': open }"
    :style="{ '--xq-main-bottom': XQ_CHART_LAYOUT.volTop }"
  >
    <button
      type="button"
      class="xq-tools-flyout__trigger"
      :class="{ 'xq-tools-flyout__trigger--on': open }"
      :aria-expanded="open"
      aria-haspopup="true"
      :title="open ? '收起工具' : '展开工具'"
      @click.stop="toggle"
    >
      <svg
        v-if="open"
        class="xq-tools-flyout__icon"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M14 7l-5 5 5 5M20 7l-5 5 5 5"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <svg v-else class="xq-tools-flyout__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M4 7l5 5-5 5M10 7l5 5-5 5"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
    <Transition name="xq-tools-slide">
      <div v-show="open" class="xq-tools-flyout__panel" role="menu">
        <KlineChartToolbar
          compact
          :fullscreen="fullscreen"
          @reset="emit('reset')"
          @zoom-in="emit('zoomIn')"
          @zoom-out="emit('zoomOut')"
          @pan-left="emit('panLeft')"
          @pan-right="emit('panRight')"
          @toggle-fullscreen="emit('toggleFullscreen')"
        />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* 锚定在主图区左下角（主图底边 ≈ volTop） */
.xq-tools-flyout {
  --xq-tools-bar-h: 22px;
  position: absolute;
  left: 6px;
  top: calc(var(--xq-main-bottom) - 2px);
  transform: translateY(-100%);
  z-index: 5;
  display: flex;
  flex-direction: row;
  align-items: stretch;
  max-width: calc(100% - 12px);
  pointer-events: none;
}

.xq-tools-flyout > * {
  pointer-events: auto;
}

.xq-tools-flyout__trigger {
  box-sizing: border-box;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: var(--xq-tools-bar-h);
  padding: 0;
  border: 0.5px solid #e8e8e8;
  border-radius: 6px;
  background: #fff;
  color: #666;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.xq-tools-flyout--open .xq-tools-flyout__trigger {
  border-radius: 6px 0 0 6px;
  border-right: none;
  box-shadow: none;
}

.xq-tools-flyout__trigger--on {
  color: v-bind('XQ.up');
}

.xq-tools-flyout__icon {
  display: block;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.xq-tools-flyout__panel {
  box-sizing: border-box;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  height: var(--xq-tools-bar-h);
  overflow: hidden;
  margin-left: 0;
  background: #fff;
  border: 0.5px solid #e8e8e8;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.xq-tools-flyout--open .xq-tools-flyout__panel {
  border-radius: 0 6px 6px 0;
  border-left: none;
}

.xq-tools-flyout__panel :deep(.xq-tools--compact) {
  height: 100%;
  min-height: 0;
}

.xq-tools-flyout__panel :deep(.xq-tools--compact .xq-tools__btn) {
  height: var(--xq-tools-bar-h);
}

.xq-tools-slide-enter-active,
.xq-tools-slide-leave-active {
  transition:
    max-width 0.2s ease,
    opacity 0.2s ease,
    margin-left 0.2s ease;
}

.xq-tools-slide-enter-from,
.xq-tools-slide-leave-to {
  max-width: 0;
  opacity: 0;
}

.xq-tools-slide-enter-to,
.xq-tools-slide-leave-from {
  max-width: 280px;
  opacity: 1;
}
</style>
