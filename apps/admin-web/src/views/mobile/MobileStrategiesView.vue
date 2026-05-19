<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import IosListGroup from '@/components/mobile/ios/IosListGroup.vue'
import IosListRow from '@/components/mobile/ios/IosListRow.vue'
import IosComplianceBanner from '@/components/mobile/ios/IosComplianceBanner.vue'
import { extractApiError } from '@/api/errors'
import {
  confirmStrategyVersion,
  generateStrategies,
  getStrategy,
  listStrategies,
  type BehaviorStrategy,
  type StrategySummary,
} from '@/api/strategies'

const props = defineProps<{
  consistencyReportId?: string | null
  period?: string
}>()

type Screen = 'list' | 'detail' | 'confirm'

const screen = ref<Screen>('list')
const summaries = ref<StrategySummary[]>([])
const detail = ref<BehaviorStrategy | null>(null)
const selectedVersionId = ref<string | null>(null)
const loading = ref(false)
const generateBusy = ref(false)
const confirmBusy = ref(false)

async function loadList() {
  loading.value = true
  try {
    const res = await listStrategies({ limit: 30 })
    summaries.value = res.data ?? []
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    loading.value = false
  }
}

async function doGenerate() {
  generateBusy.value = true
  try {
    const res = await generateStrategies({
      period: props.period ?? 'day',
      consistency_report_id: props.consistencyReportId ?? undefined,
    })
    detail.value = res.data
    selectedVersionId.value = res.data.versions[0]?.id ?? null
    screen.value = 'detail'
    await loadList()
    ElMessage.success('已生成候选策略草案')
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    generateBusy.value = false
  }
}

async function openStrategy(id: string) {
  loading.value = true
  try {
    const res = await getStrategy(id)
    detail.value = res.data
    const confirmed = res.data.versions.find((v) => v.status === 'confirmed')
    selectedVersionId.value = confirmed?.id ?? res.data.versions[0]?.id ?? null
    screen.value = 'detail'
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    loading.value = false
  }
}

async function doConfirm() {
  if (!detail.value || !selectedVersionId.value) return
  confirmBusy.value = true
  try {
    const res = await confirmStrategyVersion(detail.value.id, selectedVersionId.value)
    detail.value = res.data
    screen.value = 'confirm'
    await loadList()
    ElMessage.success('策略已确认，可进入回测验证')
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    confirmBusy.value = false
  }
}

function backToList() {
  screen.value = 'list'
  detail.value = null
}

onMounted(loadList)

defineExpose({ reload: loadList })
</script>

<template>
  <div class="strat-view">
    <IosComplianceBanner />
    <template v-if="screen === 'list'">
      <section class="strat-cta">
        <button type="button" class="strat-btn" :disabled="generateBusy" @click="doGenerate">
          {{ generateBusy ? '生成中…' : '从盲测生成候选 DSL' }}
        </button>
        <p class="strat-hint">需一致性报告达标；仅使用 blind_replay 样本，不含开卷标注。</p>
      </section>
      <div v-if="loading" class="strat-loading">加载中…</div>
      <IosListGroup v-else title="策略库">
        <IosListRow
          v-for="s in summaries"
          :key="s.id"
          :label="s.name"
          :value="`${s.status} · ${s.version_count} 版`"
          show-chevron
          @click="openStrategy(s.id)"
        />
        <p v-if="!summaries.length" class="strat-empty">暂无策略，请先完成盲测并生成草案</p>
      </IosListGroup>
    </template>

    <template v-else-if="screen === 'detail' && detail">
      <p class="strat-title">{{ detail.name }}</p>
      <p class="strat-meta">状态 {{ detail.status }} · {{ detail.period }}</p>
      <IosListGroup title="候选版本（点选后确认）">
        <button
          v-for="v in detail.versions"
          :key="v.id"
          type="button"
          class="strat-version"
          :class="{ 'is-selected': selectedVersionId === v.id }"
          @click="selectedVersionId = v.id"
        >
          <span class="strat-version__name">方案 {{ v.version_no }} · 拟合 {{ v.rank_score }}</span>
          <ul class="strat-version__rules">
            <li v-for="(line, i) in v.rules_summary" :key="i">{{ line }}</li>
          </ul>
        </button>
      </IosListGroup>
      <section class="strat-cta">
        <button
          type="button"
          class="strat-btn"
          :disabled="confirmBusy || !selectedVersionId"
          @click="doConfirm"
        >
          {{ confirmBusy ? '确认中…' : '确认此 DSL' }}
        </button>
        <button type="button" class="strat-link" @click="backToList">返回列表</button>
      </section>
    </template>

    <template v-else-if="screen === 'confirm' && detail">
      <section class="strat-done">
        <p class="strat-done__title">已确认</p>
        <p class="strat-done__text">
          行为策略「{{ detail.name }}」已进入正式状态。请切换到「回测」Tab 选择该策略并提交验证。
        </p>
        <button type="button" class="strat-link" @click="backToList">返回策略库</button>
      </section>
    </template>
  </div>
</template>

<style scoped>
.strat-view {
  padding-bottom: 16px;
}
.strat-cta {
  margin: 12px 16px;
}
.strat-btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #fff;
  background: var(--h5-tint);
}
.strat-btn:disabled {
  opacity: 0.5;
}
.strat-hint {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.4;
  color: var(--h5-label-tertiary);
  text-align: center;
}
.strat-loading,
.strat-empty {
  padding: 20px;
  text-align: center;
  color: var(--h5-label-secondary);
}
.strat-title {
  margin: 12px 16px 4px;
  font-size: 20px;
  font-weight: 700;
}
.strat-meta {
  margin: 0 16px 12px;
  font-size: 14px;
  color: var(--h5-label-secondary);
}
.strat-version {
  display: block;
  width: 100%;
  margin: 0;
  padding: 12px 16px;
  border: none;
  border-bottom: 0.5px solid var(--h5-separator);
  background: var(--h5-bg-elevated);
  text-align: left;
}
.strat-version.is-selected {
  background: rgba(0, 122, 255, 0.08);
  box-shadow: inset 0 0 0 2px var(--h5-tint);
}
.strat-version__name {
  display: block;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
}
.strat-version__rules {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--h5-label-secondary);
}
.strat-link {
  display: block;
  width: 100%;
  margin-top: 12px;
  border: none;
  background: none;
  color: var(--h5-tint);
  font-size: 15px;
}
.strat-done {
  margin: 24px 16px;
  padding: 20px;
  border-radius: 12px;
  background: var(--h5-bg-elevated);
}
.strat-done__title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
}
.strat-done__text {
  margin: 0 0 16px;
  font-size: 15px;
  line-height: 1.45;
  color: var(--h5-label-secondary);
}
</style>
