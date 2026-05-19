<script setup lang="ts">
import type { H5TabKey } from '@/mobile/h5Types'

defineProps<{
  modelValue: H5TabKey
  tabs: { key: H5TabKey; label: string }[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: H5TabKey]
}>()

function select(key: H5TabKey) {
  emit('update:modelValue', key)
}
</script>

<template>
  <nav class="ios-tab-bar" aria-label="主标签">
    <button
      v-for="t in tabs"
      :key="t.key"
      type="button"
      class="ios-tab-bar__item"
      :class="{ 'is-active': modelValue === t.key }"
      :aria-current="modelValue === t.key ? 'page' : undefined"
      @click="select(t.key)"
    >
      <span class="ios-tab-bar__icon" aria-hidden="true">
        <svg v-if="t.key === 'training'" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.6" />
          <path
            d="M10 8.5v7l5.5-3.5L10 8.5z"
            fill="currentColor"
            stroke="none"
          />
        </svg>
        <svg v-else-if="t.key === 'workspace'" viewBox="0 0 24 24" fill="none">
          <path
            d="M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-5v-7H10v7H5a1 1 0 01-1-1v-9.5z"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linejoin="round"
          />
        </svg>
        <svg v-else-if="t.key === 'labeling'" viewBox="0 0 24 24" fill="none">
          <path
            d="M4 18V6M8 18V10M12 18v-8M16 18V8M20 18V14"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
          />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none">
          <path
            d="M4 16c3-6 13-6 16 0"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
          />
          <path
            d="M6 12h3M15 9h3M9 18h6"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
        </svg>
      </span>
      <span class="ios-tab-bar__label">{{ t.label }}</span>
    </button>
  </nav>
</template>

<style scoped>
.ios-tab-bar {
  display: flex;
  flex-shrink: 0;
  min-height: calc(var(--h5-tabbar-h) + var(--h5-content-inset-bottom));
  padding-bottom: var(--h5-content-inset-bottom);
  background: rgba(249, 249, 249, 0.94);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-top: 0.5px solid var(--h5-separator);
}
.ios-tab-bar__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  margin: 0;
  padding: 6px 4px 8px;
  min-height: 50px;
  border: none;
  background: none;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--h5-label-secondary);
  cursor: pointer;
  touch-action: manipulation;
}
.ios-tab-bar__item.is-active {
  color: var(--h5-tint);
}
.ios-tab-bar__item:active {
  opacity: 0.65;
}
.ios-tab-bar__icon {
  display: flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
}
.ios-tab-bar__icon svg {
  width: 26px;
  height: 26px;
}
</style>
