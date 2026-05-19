import { onMounted, ref } from 'vue'
import type { SymbolItem } from '@/api/market'

const STORAGE_KEY = 'iquant_h5_recent_symbols'
const MAX_ITEMS = 12

function readStored(): SymbolItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (x): x is SymbolItem =>
          x !== null &&
          typeof x === 'object' &&
          typeof (x as SymbolItem).full_code === 'string' &&
          typeof (x as SymbolItem).name === 'string',
      )
      .slice(0, MAX_ITEMS)
  } catch {
    return []
  }
}

function writeStored(items: SymbolItem[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)))
  } catch {
    /* ignore quota / private mode */
  }
}

/** 标注页「最近使用标的」，持久化在 localStorage。 */
export function useH5RecentSymbols() {
  const recent = ref<SymbolItem[]>([])

  function load() {
    recent.value = readStored()
  }

  function remember(sym: SymbolItem) {
    const next = [
      sym,
      ...recent.value.filter((s) => s.full_code !== sym.full_code),
    ].slice(0, MAX_ITEMS)
    recent.value = next
    writeStored(next)
  }

  onMounted(load)

  return { recent, remember, load }
}
