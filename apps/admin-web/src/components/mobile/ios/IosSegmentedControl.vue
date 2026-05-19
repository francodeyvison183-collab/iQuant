<script setup lang="ts">
const model = defineModel<string>({ required: true })

defineProps<{
  options: { value: string; label: string }[]
}>()
</script>

<template>
  <div class="ios-seg" role="tablist">
    <button
      v-for="opt in options"
      :key="opt.value"
      type="button"
      role="tab"
      class="ios-seg__btn"
      :class="{ 'is-selected': model === opt.value }"
      :aria-selected="model === opt.value"
      @click="model = opt.value"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<style scoped>
.ios-seg {
  display: flex;
  padding: 2px;
  border-radius: 9px;
  background: rgba(118, 118, 128, 0.12);
  gap: 2px;
}
.ios-seg__btn {
  flex: 1;
  margin: 0;
  padding: 8px 6px;
  min-height: 32px;
  border: none;
  border-radius: 7px;
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--h5-label-primary);
  cursor: pointer;
  touch-action: manipulation;
}
.ios-seg__btn.is-selected {
  background: var(--h5-bg-elevated);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.08), 0 1px 1px rgba(0, 0, 0, 0.06);
}
.ios-seg__btn:active {
  opacity: 0.88;
}
</style>
