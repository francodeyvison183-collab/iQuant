<script setup lang="ts">
defineProps<{
  title?: string
  footer?: string
}>()
</script>

<template>
  <section class="ios-group">
    <p v-if="title" class="ios-group__header">{{ title }}</p>
    <p v-else-if="$slots.header" class="ios-group__header">
      <slot name="header" />
    </p>
    <div class="ios-group__card">
      <slot />
    </div>
    <p v-if="footer" class="ios-group__footer">{{ footer }}</p>
  </section>
</template>

<style scoped>
.ios-group {
  margin-bottom: var(--h5-group-gap);
}
.ios-group__header {
  margin: 0 16px 6px;
  font-size: 13px;
  line-height: 1.3;
  color: var(--h5-label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.ios-group__card {
  margin: 0 16px;
  border-radius: var(--h5-radius-cell);
  overflow: hidden;
  box-shadow: 0 0.5px 0 var(--h5-separator);
}
.ios-group__card > :deep(*:not(:last-child)) {
  border-bottom: 0.5px solid var(--h5-separator);
}
.ios-group__footer {
  margin: 8px 16px 0;
  font-size: 13px;
  line-height: 1.35;
  color: var(--h5-label-secondary);
}
</style>
