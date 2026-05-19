<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import IosNavBar from '@/components/mobile/ios/IosNavBar.vue'
import IosListGroup from '@/components/mobile/ios/IosListGroup.vue'
import IosListRow from '@/components/mobile/ios/IosListRow.vue'
import IosComplianceBanner from '@/components/mobile/ios/IosComplianceBanner.vue'
import MobileBlindChart from '@/views/mobile/MobileBlindChart.vue'
import MobileStrategiesView from '@/views/mobile/MobileStrategiesView.vue'
import { extractApiError } from '@/api/errors'
import { BLIND_KLINE_PERIOD_OPTIONS } from '@/chart/klinePeriod'
import {
  createBlindSession,
  evaluateConsistencyReport,
  getConsistencyReport,
  listBlindRounds,
  skipBlindSession,
  type BlindConsistencyReport,
  type BlindRound,
  type BlindSessionDetail,
} from '@/api/replays'

type TrainScreen = 'home' | 'play' | 'report' | 'strategy' | 'history'

const screen = ref<TrainScreen>('home')
const chartPeriod = ref('day')
const sessionId = ref<string | null>(null)
const sessionDetail = ref<BlindSessionDetail | null>(null)
const startBusy = ref(false)

function defaultDateRange(): { start: string; end: string } {
  const today = new Date()
  const end = today.toISOString().slice(0, 10)
  const past = new Date(today)
  past.setMonth(past.getMonth() - 6)
  return { start: past.toISOString().slice(0, 10), end }
}
const _dr = defaultDateRange()
const rangeStart = ref<string>(_dr.start)
const rangeEnd = ref<string>(_dr.end)
const today = computed(() => new Date().toISOString().slice(0, 10))
const report = ref<BlindConsistencyReport | null>(null)
const reportLoading = ref(false)
const rounds = ref<BlindRound[]>([])
const historyLoading = ref(false)

const periodOptions = BLIND_KLINE_PERIOD_OPTIONS.map((p) => ({ value: p.value, label: p.label }))

function sessionTitle(d: BlindSessionDetail | null): string {
  if (!d) return '盲测训练'
  const code = d.display_label
  const name = d.display_name
  return name ? `${code} · ${name}` : code
}

const navTitle = computed(() => {
  if (screen.value === 'play') return sessionTitle(sessionDetail.value)
  if (screen.value === 'report') return '一致性报告'
  if (screen.value === 'strategy') return '生成策略'
  if (screen.value === 'history') return '训练记录'
  return '盲测训练'
})

const roundStatusLabel: Record<string, string> = {
  active: '进行中',
  finished: '已完成',
  abandoned: '已放弃',
}

function roundTitle(r: BlindRound): string {
  const date = r.started_at?.slice(0, 10) ?? ''
  return `${date} · 第 ${rounds.value.length - rounds.value.indexOf(r)} 轮`
}

function roundRowValue(r: BlindRound): string {
  const status = roundStatusLabel[r.status] ?? r.status
  return `${status} · ${r.trade_action_count}/${r.required_trade_actions} 次 · ${r.stock_count} 只`
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await listBlindRounds({ limit: 30 })
    rounds.value = res.data ?? []
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    historyLoading.value = false
  }
}

function toIsoStart(d: string): string {
  return `${d}T00:00:00Z`
}

function toIsoEnd(d: string): string {
  return `${d}T23:59:59Z`
}

function validateRange(): boolean {
  if (!rangeStart.value || !rangeEnd.value) {
    ElMessage.warning('请选择训练的开始与结束日期')
    return false
  }
  if (rangeEnd.value <= rangeStart.value) {
    ElMessage.warning('结束日期必须晚于开始日期')
    return false
  }
  return true
}

async function startSession() {
  if (!validateRange()) return
  startBusy.value = true
  try {
    const res = await createBlindSession({
      period: chartPeriod.value,
      range_start: toIsoStart(rangeStart.value),
      range_end: toIsoEnd(rangeEnd.value),
    })
    sessionId.value = res.data.id
    sessionDetail.value = res.data
    screen.value = 'play'
    ElMessage.success(`已分配 ${sessionTitle(res.data)}，请完成 ${res.data.required_trade_actions} 次买入或卖出`)
  } catch (e) {
    ElMessage.error(extractApiError(e))
  } finally {
    startBusy.value = false
  }
}

async function onSessionUpdated(d: BlindSessionDetail) {
  sessionDetail.value = d
}

async function onSessionFinished() {
  const status = sessionDetail.value?.status
  if (status === 'finished') {
    ElMessage.success('恭喜，本轮 10 次买卖已完成')
    goHome()
    return
  }
  if (status === 'abandoned') {
    ElMessage.warning('本轮已放弃')
    goHome()
    return
  }
  // switched 等其他情况：自动分配下一只继续本轮
  await startSession()
}

async function onSkip(payload: { tradeCount: number } = { tradeCount: 0 }) {
  const tradeCount = payload.tradeCount ?? 0
  const hasTrades = tradeCount > 0
  const title = hasTrades ? '切换下一只' : '跳过本只'
  const message = hasTrades
    ? `当前已在本只操作 ${tradeCount} 次，切换后会继续本轮累计（不会清零）。`
    : '该股不合适，跳过后随机分配下一只，本轮买卖次数不变。'
  try {
    await ElMessageBox.confirm(message, title, {
      confirmButtonText: hasTrades ? '切换' : '跳过',
      cancelButtonText: '继续训练',
      type: 'warning',
    })
  } catch {
    return
  }
  if (sessionId.value) {
    try {
      await skipBlindSession(sessionId.value)
    } catch (e) {
      ElMessage.error(extractApiError(e))
      return
    }
  }
  await startSession()
}

function onPeriodChange(next: string) {
  if (next === chartPeriod.value) return
  chartPeriod.value = next
}

async function openReport(regenerate = false) {
  reportLoading.value = true
  screen.value = 'report'
  try {
    let res
    if (regenerate) {
      res = await evaluateConsistencyReport({ period: chartPeriod.value, regenerate: true })
    } else {
      try {
        res = await getConsistencyReport(chartPeriod.value)
      } catch {
        res = await evaluateConsistencyReport({ period: chartPeriod.value })
      }
    }
    report.value = res.data
  } catch (e) {
    ElMessage.error(extractApiError(e))
    screen.value = 'home'
  } finally {
    reportLoading.value = false
  }
}

function goHome() {
  screen.value = 'home'
  sessionId.value = null
  sessionDetail.value = null
}

function onNavBack() {
  if (screen.value === 'strategy') {
    screen.value = 'report'
    return
  }
  if (screen.value === 'play') {
    void ElMessageBox.confirm('离开将中断当前训练，确定返回？', '返回', {
      confirmButtonText: '返回',
      cancelButtonText: '继续',
      type: 'warning',
    }).then(() => goHome()).catch(() => {})
    return
  }
  goHome()
}

function goStrategy() {
  if (!report.value?.ready_for_strategy) {
    ElMessage.warning('一致性未达标，请继续盲测训练')
    return
  }
  screen.value = 'strategy'
}

function goHistory() {
  screen.value = 'history'
  loadHistory()
}

onMounted(() => {
  loadHistory()
})
</script>

<template>
  <div class="bt-train-page">
    <IosNavBar
      :title="navTitle"
      :show-back="screen !== 'home'"
      @back="onNavBack"
    />
    <div class="bt-train-body">
      <template v-if="screen === 'home'">
        <IosComplianceBanner />
        <section class="bt-train-hero">
          <p class="bt-train-hero__badge">方案 A · 主路径</p>
          <h1 class="bt-train-hero__title">近端历史盲测</h1>
          <p class="bt-train-hero__sub">
            系统随机分配脱敏标的；一轮训练 = 跨多只累计 10 次买入或卖出。中途随时可切换下一只，已完成的次数继续计入本轮；观望不计入次数。
          </p>
        </section>
        <IosListGroup title="K 线周期">
          <div class="bt-period-row">
            <button
              v-for="p in periodOptions"
              :key="p.value"
              type="button"
              class="bt-period-btn"
              :class="{ 'is-active': chartPeriod === p.value }"
              @click="chartPeriod = p.value"
            >
              {{ p.label }}
            </button>
          </div>
        </IosListGroup>
        <IosListGroup title="训练区间">
          <div class="bt-date-row">
            <label class="bt-date-field">
              <span class="bt-date-label">开始日期</span>
              <input
                v-model="rangeStart"
                type="date"
                class="bt-date-input"
                :max="rangeEnd || today"
              />
            </label>
            <label class="bt-date-field">
              <span class="bt-date-label">结束日期</span>
              <input
                v-model="rangeEnd"
                type="date"
                class="bt-date-input"
                :min="rangeStart"
                :max="today"
              />
            </label>
          </div>
          <p class="bt-date-hint">该区间内的所有股票共享一轮 10 次买卖，跨股累计完成即算完成本轮。</p>
        </IosListGroup>
        <section class="bt-train-cta">
          <button type="button" class="bt-train-cta__btn" :disabled="startBusy" @click="startSession">
            {{ startBusy ? '分配中…' : '开始训练' }}
          </button>
        </section>
        <IosListGroup title="更多">
          <IosListRow label="一致性报告" value="≥3 轮后生成" show-chevron @click="openReport(false)" />
          <IosListRow label="训练记录" value="历史会话" show-chevron @click="goHistory" />
        </IosListGroup>
      </template>

      <template v-else-if="screen === 'play' && sessionId">
        <MobileBlindChart
          :session-id="sessionId"
          :period="chartPeriod"
          @updated="onSessionUpdated"
          @finished="onSessionFinished"
          @skip="onSkip"
          @update:period="onPeriodChange"
        />
      </template>

      <template v-else-if="screen === 'report'">
        <div v-if="reportLoading" class="bt-loading">加载中…</div>
        <template v-else-if="report">
          <section class="bt-report-hero">
            <p class="bt-report-score">综合 {{ report.scores.overall ?? '—' }} 分</p>
            <p class="bt-report-draft">{{ report.profile_draft }}</p>
          </section>
          <IosListGroup title="分项">
            <IosListRow label="入场一致性" :value="String(report.scores.entry_consistency ?? '—')" />
            <IosListRow label="节奏一致性" :value="String(report.scores.rhythm_consistency ?? '—')" />
            <IosListRow label="已完成轮次" :value="String(report.session_count)" />
            <IosListRow
              label="可生成策略草案"
              :value="report.ready_for_strategy ? '是' : '否'"
            />
          </IosListGroup>
          <IosListGroup title="说明">
            <p v-for="(line, i) in report.insights" :key="i" class="bt-insight">{{ line }}</p>
          </IosListGroup>
          <section class="bt-train-cta">
            <button
              v-if="report.ready_for_strategy"
              type="button"
              class="bt-train-cta__btn"
              @click="goStrategy"
            >
              生成并确认行为策略 DSL
            </button>
            <button type="button" class="bt-train-cta__btn bt-train-cta__btn--secondary" @click="openReport(true)">
              重新评估
            </button>
          </section>
        </template>
      </template>

      <template v-else-if="screen === 'strategy'">
        <MobileStrategiesView
          :period="chartPeriod"
          :consistency-report-id="report?.id ?? null"
        />
      </template>

      <template v-else-if="screen === 'history'">
        <div v-if="historyLoading" class="bt-loading">加载中…</div>
        <IosListGroup v-else title="轮次">
          <IosListRow
            v-for="r in rounds"
            :key="r.round_id"
            :label="roundTitle(r)"
            :value="roundRowValue(r)"
          />
          <p v-if="!rounds.length" class="bt-empty">暂无记录</p>
        </IosListGroup>
      </template>
    </div>
  </div>
</template>

<style scoped>
.bt-train-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
  background: var(--h5-bg-grouped);
}
.bt-train-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  -webkit-overflow-scrolling: touch;
}
.bt-train-hero {
  margin: 0 16px 20px;
}
.bt-train-hero__badge {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--h5-tint);
}
.bt-train-hero__title {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 700;
  color: var(--h5-label-primary);
}
.bt-train-hero__sub {
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
  color: var(--h5-label-secondary);
}
.bt-train-cta {
  margin: 16px;
}
.bt-train-cta__btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 17px;
  font-weight: 600;
  color: #fff;
  background: var(--h5-tint);
}
.bt-train-cta__btn--secondary {
  margin-top: 10px;
  background: var(--h5-bg-elevated);
  color: var(--h5-tint);
}
.bt-period-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 12px 16px;
}
.bt-period-btn {
  padding: 8px 14px;
  border-radius: 8px;
  border: none;
  background: var(--h5-bg-elevated);
  font-size: 14px;
}
.bt-period-btn.is-active {
  background: var(--h5-tint);
  color: #fff;
}
.bt-date-row {
  display: flex;
  gap: 12px;
  padding: 12px 16px 4px;
}
.bt-date-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.bt-date-label {
  font-size: 12px;
  color: var(--h5-label-secondary);
}
.bt-date-input {
  appearance: none;
  -webkit-appearance: none;
  border: 1px solid var(--h5-separator, #d0d0d6);
  border-radius: 8px;
  background: var(--h5-bg-elevated);
  padding: 10px 12px;
  font-size: 15px;
  color: var(--h5-label-primary);
  width: 100%;
  box-sizing: border-box;
}
.bt-date-hint {
  margin: 4px 16px 12px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--h5-label-secondary);
}
.bt-report-hero {
  margin: 16px;
  padding: 16px;
  border-radius: 12px;
  background: var(--h5-bg-elevated);
}
.bt-report-score {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
}
.bt-report-draft {
  margin: 0;
  font-size: 15px;
  line-height: 1.45;
  color: var(--h5-label-secondary);
}
.bt-insight {
  margin: 0;
  padding: 10px 16px;
  font-size: 14px;
  line-height: 1.4;
  color: var(--h5-label-secondary);
}
.bt-loading,
.bt-empty {
  padding: 24px;
  text-align: center;
  color: var(--h5-label-secondary);
}
</style>
