<script setup lang="ts">
import { ref } from 'vue'
import '@/styles/h5-ios-tokens.css'
import MobileBlindTrainingView from './MobileBlindTrainingView.vue'
import MobileWorkspaceView from './MobileWorkspaceView.vue'
import MobileLabelingView from './MobileLabelingView.vue'
import MobileBacktestView from './MobileBacktestView.vue'
import IosBottomTabBar from '@/components/mobile/ios/IosBottomTabBar.vue'
import type { H5TabKey } from '@/mobile/h5Types'

const activeTab = ref<H5TabKey>('training')

const tabs: { key: H5TabKey; label: string }[] = [
  { key: 'training', label: '训练' },
  { key: 'workspace', label: '工作台' },
  { key: 'backtest', label: '回测' },
  { key: 'labeling', label: '高级' },
]
</script>

<template>
  <div class="h5-app h5-ios">
    <div class="h5-main">
      <MobileBlindTrainingView v-show="activeTab === 'training'" />
      <MobileWorkspaceView v-show="activeTab === 'workspace'" @switch-tab="activeTab = $event" />
      <MobileBacktestView v-show="activeTab === 'backtest'" />
      <MobileLabelingView v-show="activeTab === 'labeling'" />
    </div>
    <IosBottomTabBar v-model="activeTab" :tabs="tabs" />
  </div>
</template>

<style scoped>
.h5-app {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--h5-bg-grouped);
}
.h5-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
