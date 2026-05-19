<script setup lang="ts">
defineProps<{
  label: string
  value?: string
  showChevron?: boolean
}>()

const emit = defineEmits<{
  click: []
}>()
</script>

<template>
  <button
    type="button"
    class="ios-row"
    :class="{ 'ios-row--nav': showChevron || $slots.default }"
    @click="emit('click')"
  >
    <span class="ios-row__label">{{ label }}</span>
    <span v-if="value" class="ios-row__value">{{ value }}</span>
    <slot />
    <span v-if="showChevron" class="ios-row__chevron" aria-hidden="true">›</span>
  </button>
</template>

<style scoped>
.ios-row {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: var(--h5-row-h);
  margin: 0;
  padding: 10px 16px;
  box-sizing: border-box;
  border: none;
  background: var(--h5-bg-elevated);
  font-size: 17px;
  text-align: left;
  color: var(--h5-label-primary);
  cursor: pointer;
  touch-action: manipulation;
  gap: 8px;
}
.ios-row--nav:active {
  background: rgba(0, 0, 0, 0.04);
}
.ios-row__label {
  flex: 1;
  min-width: 0;
}
.ios-row__value {
  font-size: 17px;
  color: var(--h5-label-secondary);
  text-align: right;
}
.ios-row__chevron {
  flex-shrink: 0;
  font-size: 20px;
  color: var(--h5-label-tertiary);
  font-weight: 300;
}
</style>
