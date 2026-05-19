<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { listSymbols, type SymbolItem } from '@/api/market'

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  recent: SymbolItem[]
}>()

const emit = defineEmits<{
  pick: [symbol: SymbolItem]
}>()

const keyword = ref('')
const market = ref<string>('')
const results = ref<SymbolItem[]>([])
const loading = ref(false)

const marketTabs = [
  { value: '', label: '全部' },
  { value: 'sh', label: '沪市' },
  { value: 'sz', label: '深市' },
  { value: 'bj', label: '北交所' },
]

let debounceTimer: ReturnType<typeof setTimeout> | null = null

async function runSearch() {
  const kw = keyword.value.trim()
  loading.value = true
  try {
    const env = await listSymbols({
      market: market.value || undefined,
      keyword: kw || undefined,
      limit: kw ? 50 : 25,
      offset: 0,
      scope: 'with_bars',
    })
    results.value = env.data ?? []
  } finally {
    loading.value = false
  }
}

function scheduleSearch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debounceTimer = null
    void runSearch()
  }, 280)
}

watch(
  () => open.value,
  (isOpen, wasOpen) => {
    if (isOpen && !wasOpen) {
      keyword.value = ''
      market.value = ''
      void runSearch()
    }
  },
)

watch([keyword, market], () => {
  if (!open.value) return
  scheduleSearch()
})

function onPick(row: SymbolItem) {
  emit('pick', row)
  open.value = false
}

function close() {
  open.value = false
}

const displayLine = (s: SymbolItem) =>
  s.name ? `${s.full_code} · ${s.name}` : s.full_code

const hasRecent = computed(() => props.recent.length > 0)
</script>

<template>
  <Teleport to="#h5-shell-portal" defer>
    <div v-if="open" class="sheet-root" aria-modal="true" role="dialog">
      <button type="button" class="sheet-scrim" aria-label="关闭" @click="close" />
      <div class="sheet-panel">
        <div class="sheet-grabber" aria-hidden="true" />
        <header class="sheet-head">
          <button type="button" class="sheet-head__btn" @click="close">取消</button>
          <span class="sheet-head__title">选择标的</span>
          <span class="sheet-head__spacer" />
        </header>
        <div class="sheet-search">
          <span class="sheet-search__icon" aria-hidden="true">⌕</span>
          <input
            v-model="keyword"
            class="sheet-search__input"
            type="search"
            enterkeyhint="search"
            autocomplete="off"
            autocapitalize="off"
            placeholder="代码或名称，如 300750 或 宁德"
          />
        </div>
        <div class="sheet-markets">
          <button
            v-for="m in marketTabs"
            :key="m.value || 'all'"
            type="button"
            class="sheet-chip"
            :class="{ 'is-on': market === m.value }"
            @click="market = m.value"
          >
            {{ m.label }}
          </button>
        </div>
        <p class="sheet-tip">仅列出已有 K 线入库的标的（与「数据查看」一致）。</p>

        <div class="sheet-scroll">
          <section v-if="hasRecent && !keyword.trim()" class="sheet-section">
            <h3 class="sheet-section__title">最近使用</h3>
            <ul class="sheet-list">
              <li v-for="r in recent" :key="r.full_code">
                <button type="button" class="sheet-row" @click="onPick(r)">
                  <span class="sheet-row__main">{{ displayLine(r) }}</span>
                  <span class="sheet-row__chev" aria-hidden="true">›</span>
                </button>
              </li>
            </ul>
          </section>

          <section class="sheet-section">
            <h3 class="sheet-section__title">
              {{ keyword.trim() ? '搜索结果' : '有 K 线的标的（前 25 条）' }}
            </h3>
            <p v-if="loading" class="sheet-muted">加载中…</p>
            <p v-else-if="!results.length" class="sheet-muted">
              无匹配标的，请尝试其它关键词或先在「数据更新」中导入行情。
            </p>
            <ul v-else class="sheet-list">
              <li v-for="s in results" :key="s.full_code">
                <button type="button" class="sheet-row" @click="onPick(s)">
                  <span class="sheet-row__main">{{ displayLine(s) }}</span>
                  <span class="sheet-row__chev" aria-hidden="true">›</span>
                </button>
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.sheet-root {
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: auto;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif;
}
.sheet-scrim {
  position: absolute;
  inset: 0;
  margin: 0;
  border: none;
  background: rgba(0, 0, 0, 0.4);
  cursor: pointer;
}
.sheet-panel {
  position: relative;
  width: 100%;
  max-height: min(76%, 640px);
  display: flex;
  flex-direction: column;
  background: #f2f2f7;
  border-radius: 12px 12px 0 0;
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.12);
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
.sheet-grabber {
  width: 36px;
  height: 5px;
  margin: 8px auto 4px;
  border-radius: 100px;
  background: rgba(60, 60, 67, 0.3);
}
.sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px 8px;
  border-bottom: 0.5px solid rgba(60, 60, 67, 0.29);
  background: #f2f2f7;
}
.sheet-head__btn {
  min-width: 56px;
  min-height: 44px;
  padding: 0 12px;
  border: none;
  background: none;
  font-size: 17px;
  color: #007aff;
  cursor: pointer;
  touch-action: manipulation;
}
.sheet-head__btn:active {
  opacity: 0.55;
}
.sheet-head__title {
  font-size: 17px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
}
.sheet-head__spacer {
  width: 56px;
}
.sheet-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 16px 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: rgba(118, 118, 128, 0.12);
}
.sheet-search__icon {
  font-size: 16px;
  color: rgba(60, 60, 67, 0.45);
}
.sheet-search__input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  font-size: 17px;
  outline: none;
  color: rgba(0, 0, 0, 0.85);
}
.sheet-markets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 16px 8px;
}
.sheet-chip {
  margin: 0;
  padding: 6px 12px;
  min-height: 32px;
  border: none;
  border-radius: 8px;
  background: #fff;
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.75);
  cursor: pointer;
  box-shadow: 0 0 0 0.5px rgba(60, 60, 67, 0.18);
  touch-action: manipulation;
}
.sheet-chip.is-on {
  background: #007aff;
  color: #fff;
  box-shadow: none;
}
.sheet-chip:active {
  opacity: 0.85;
}
.sheet-tip {
  margin: 0 16px 8px;
  font-size: 12px;
  line-height: 1.35;
  color: rgba(60, 60, 67, 0.55);
}
.sheet-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 12px;
}
.sheet-section {
  margin-bottom: 16px;
}
.sheet-section__title {
  margin: 8px 16px 6px;
  font-size: 13px;
  font-weight: 600;
  color: rgba(60, 60, 67, 0.55);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.sheet-list {
  list-style: none;
  margin: 0 16px;
  padding: 0;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 0.5px 0 rgba(60, 60, 67, 0.29);
}
.sheet-list li + li {
  border-top: 0.5px solid rgba(60, 60, 67, 0.29);
}
.sheet-row {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 48px;
  padding: 10px 14px;
  border: none;
  background: #fff;
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
  gap: 8px;
}
.sheet-row:active {
  background: rgba(0, 0, 0, 0.04);
}
.sheet-row__main {
  flex: 1;
  min-width: 0;
  font-size: 16px;
  color: rgba(0, 0, 0, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sheet-row__chev {
  flex-shrink: 0;
  font-size: 18px;
  color: rgba(60, 60, 67, 0.3);
}
.sheet-muted {
  margin: 8px 16px;
  font-size: 15px;
  color: rgba(60, 60, 67, 0.55);
}
</style>
