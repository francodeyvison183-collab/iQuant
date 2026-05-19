<script setup lang="ts">
import { ref } from 'vue'
import IosNavBar from '@/components/mobile/ios/IosNavBar.vue'
import IosListGroup from '@/components/mobile/ios/IosListGroup.vue'
import IosListRow from '@/components/mobile/ios/IosListRow.vue'
import IosComplianceBanner from '@/components/mobile/ios/IosComplianceBanner.vue'
import MobileStrategiesView from '@/views/mobile/MobileStrategiesView.vue'
import type { H5TabKey } from '@/mobile/h5Types'

type WorkspaceScreen = 'home' | 'strategies'

const screen = ref<WorkspaceScreen>('home')

const emit = defineEmits<{
  switchTab: [tab: H5TabKey]
}>()

function goStrategies() {
  screen.value = 'strategies'
}

function goHome() {
  screen.value = 'home'
}
</script>

<template>
  <div class="ws-page">
    <IosNavBar
      :title="screen === 'home' ? '工作台' : '行为策略'"
      :show-back="screen !== 'home'"
      @back="goHome"
    />
    <div class="ws-body">
      <template v-if="screen === 'home'">
        <IosComplianceBanner />
        <section class="ws-hero">
          <p class="ws-hero__title">欢迎回来</p>
          <p class="ws-hero__sub">
            主路径：多轮近端历史盲测 → 跨轮一致性 → 行为策略 DSL → 回测与优化建议。从下栏「训练」开始。
          </p>
        </section>
        <IosListGroup title="快速开始">
          <IosListRow
            label="盲测训练"
            value="方案 A 主路径"
            show-chevron
            @click="emit('switchTab', 'training')"
          />
          <IosListRow
            label="回测报告"
            value="查看验证结果"
            show-chevron
            @click="emit('switchTab', 'backtest')"
          />
        </IosListGroup>
        <IosListGroup title="策略资产" footer="由盲测行为归纳 DSL，规则可解释；非黑盒荐股信号。">
          <IosListRow
            label="行为策略库"
            value="生成与确认 DSL"
            show-chevron
            @click="goStrategies"
          />
          <IosListRow
            label="K 线对照标注"
            value="高级 · 开卷补录"
            show-chevron
            @click="emit('switchTab', 'labeling')"
          />
        </IosListGroup>
        <IosListGroup title="最近动态（占位）">
          <IosListRow label="进行中盲测会话" value="—" />
          <IosListRow label="最近回测任务" value="—" />
        </IosListGroup>
      </template>
      <template v-else>
        <MobileStrategiesView />
      </template>
    </div>
  </div>
</template>

<style scoped>
.ws-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--h5-bg-grouped);
}
.ws-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding-bottom: 12px;
  -webkit-overflow-scrolling: touch;
}
.ws-hero {
  margin: 0 16px 20px;
}
.ws-hero__title {
  margin: 0 0 6px;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 0.02em;
  line-height: 1.1;
  color: var(--h5-label-primary);
}
.ws-hero__sub {
  margin: 0;
  font-size: 15px;
  line-height: 1.4;
  color: var(--h5-label-secondary);
}
</style>
