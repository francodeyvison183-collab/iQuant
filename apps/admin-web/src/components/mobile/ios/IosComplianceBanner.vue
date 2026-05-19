<script setup lang="ts">
import { ref } from 'vue'

const expanded = ref(false)
</script>

<template>
  <aside class="ios-compliance">
    <button type="button" class="ios-compliance__toggle" @click="expanded = !expanded">
      <span class="ios-compliance__icon" aria-hidden="true">!</span>
      <span class="ios-compliance__text">
        本产品为策略验证与训练工具，不构成投资建议；历史表现不代表未来收益。
      </span>
      <span class="ios-compliance__caret" aria-hidden="true">{{ expanded ? '▴' : '▾' }}</span>
    </button>
    <p v-if="expanded" class="ios-compliance__more">
      K 线标注用于表达你的交易逻辑并生成可回测策略，不构成投资建议。盲测与回测结果仅基于历史数据，无法替代真实交易中的风险与心理因素。
    </p>
  </aside>
</template>

<style scoped>
.ios-compliance {
  margin: 0 16px 16px;
  border-radius: var(--h5-radius-cell);
  background: rgba(255, 204, 0, 0.12);
  border: 0.5px solid rgba(255, 159, 10, 0.35);
  overflow: hidden;
}
.ios-compliance__toggle {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  margin: 0;
  padding: 10px 12px;
  border: none;
  background: transparent;
  font-size: 13px;
  line-height: 1.35;
  color: var(--h5-label-primary);
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
}
.ios-compliance__toggle:active {
  background: rgba(0, 0, 0, 0.03);
}
.ios-compliance__icon {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255, 159, 10, 0.9);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.ios-compliance__text {
  flex: 1;
  min-width: 0;
}
.ios-compliance__caret {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--h5-label-secondary);
  margin-top: 3px;
}
.ios-compliance__more {
  margin: 0;
  padding: 0 12px 12px 40px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--h5-label-secondary);
}
</style>
