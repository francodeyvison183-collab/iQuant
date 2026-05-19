<script setup lang="ts">
defineProps<{
  title: string
  showBack?: boolean
}>()

const emit = defineEmits<{
  back: []
}>()
</script>

<template>
  <header class="ios-nav-bar">
    <div class="ios-nav-bar__inner">
      <button
        v-if="showBack"
        type="button"
        class="ios-nav-bar__back"
        aria-label="返回"
        @click="emit('back')"
      >
        <span class="ios-nav-bar__chevron" aria-hidden="true">‹</span>
        返回
      </button>
      <h1 class="ios-nav-bar__title">{{ title }}</h1>
      <div v-if="$slots.trailing" class="ios-nav-bar__trailing">
        <slot name="trailing" />
      </div>
    </div>
  </header>
</template>

<style scoped>
.ios-nav-bar {
  flex-shrink: 0;
  padding: var(--h5-content-inset-top) 12px 8px;
  background: var(--h5-bg-grouped);
  border-bottom: 0.5px solid var(--h5-separator);
}
.ios-nav-bar__inner {
  position: relative;
  min-height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ios-nav-bar__back {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin: 0;
  padding: 0 8px 0 4px;
  min-height: 44px;
  border: none;
  background: none;
  font-size: 17px;
  font-weight: 400;
  color: var(--h5-tint);
  cursor: pointer;
  touch-action: manipulation;
}
.ios-nav-bar__back:active {
  opacity: 0.55;
}
.ios-nav-bar__chevron {
  font-size: 22px;
  font-weight: 400;
  line-height: 1;
  margin-top: -2px;
}
.ios-nav-bar__title {
  margin: 0;
  max-width: 60%;
  font-size: 17px;
  font-weight: 600;
  text-align: center;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ios-nav-bar__inner:has(.ios-nav-bar__trailing) .ios-nav-bar__title {
  max-width: calc(100% - 120px);
}

.ios-nav-bar__trailing {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 44px;
  z-index: 2;
}
</style>
