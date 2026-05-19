<script setup lang="ts">
defineProps<{
  fullscreen?: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  reset: []
  zoomIn: []
  zoomOut: []
  panLeft: []
  panRight: []
  toggleFullscreen: []
}>()
</script>

<template>
  <div
    class="xq-tools"
    :class="{ 'xq-tools--compact': compact }"
    role="toolbar"
    aria-label="K线工具"
  >
    <button type="button" class="xq-tools__btn" title="复位" @click="emit('reset')">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 4a8 8 0 1 0 7.75 6M12 8V4M12 8l2.5-2.5M12 8L9.5 5.5"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
    <button type="button" class="xq-tools__btn" title="放大" @click="emit('zoomIn')">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.5" />
        <path d="M14.5 14.5L20 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <path d="M10 7.5v5M7.5 10h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
    </button>
    <button type="button" class="xq-tools__btn" title="缩小" @click="emit('zoomOut')">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="6.5" stroke="currentColor" stroke-width="1.5" />
        <path d="M14.5 14.5L20 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        <path d="M7.5 10h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
    </button>
    <button type="button" class="xq-tools__btn" title="向左" @click="emit('panLeft')">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M14 6L8 12l6 6"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
    <button type="button" class="xq-tools__btn" title="向右" @click="emit('panRight')">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M10 6l6 6-6 6"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
    <button
      type="button"
      class="xq-tools__btn"
      :title="fullscreen ? '退出全屏' : '全屏'"
      @click="emit('toggleFullscreen')"
    >
      <svg v-if="!fullscreen" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M8 4H4v4M16 4h4v4M8 20H4v-4M16 20h4v-4"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <svg v-else viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M9 9H5V5M15 9h4V5M9 15H5v4M15 15h4v4"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.xq-tools {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-end;
  gap: 0;
  width: 100%;
  min-height: 36px;
  padding: 0 4px;
  background: #fff;
  border-bottom: 0.5px solid #eee;
}

.xq-tools--compact {
  width: auto;
  min-height: 0;
  padding: 0;
  border-bottom: none;
  flex-shrink: 0;
  gap: 0;
}

.xq-tools__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 36px;
  padding: 0;
  border: none;
  border-right: 0.5px solid #f0f0f0;
  background: transparent;
  color: #555;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.xq-tools--compact .xq-tools__btn {
  width: 22px;
  height: 22px;
  border-right: none;
  color: #666;
}

.xq-tools__btn:last-child {
  border-right: none;
}

.xq-tools__btn:active {
  background: #f5f5f5;
  color: #333;
}

.xq-tools__btn svg {
  width: 20px;
  height: 20px;
}

.xq-tools--compact .xq-tools__btn svg {
  width: 12px;
  height: 12px;
}
</style>
