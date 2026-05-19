/** 前端技术指标（标注 K 线展示用，非交易信号）。 */

export function sma(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  let sum = 0
  for (let i = 0; i < values.length; i++) {
    sum += values[i]
    if (i >= period) sum -= values[i - period]
    out.push(i >= period - 1 ? sum / period : null)
  }
  return out
}

export function ema(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  const k = 2 / (period + 1)
  let prev: number | null = null
  for (let i = 0; i < values.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    if (prev === null) {
      const seed = values.slice(0, period).reduce((a, b) => a + b, 0) / period
      prev = seed
      out.push(seed)
      continue
    }
    prev = values[i] * k + prev * (1 - k)
    out.push(prev)
  }
  return out
}

export function boll(
  values: number[],
  period: number,
  mult: number,
): { upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] } {
  const mid = sma(values, period)
  const upper: (number | null)[] = []
  const lower: (number | null)[] = []
  for (let i = 0; i < values.length; i++) {
    const m = mid[i]
    if (m === null) {
      upper.push(null)
      lower.push(null)
      continue
    }
    const start = i - period + 1
    let variance = 0
    for (let j = start; j <= i; j++) {
      const d = values[j] - m
      variance += d * d
    }
    const std = Math.sqrt(variance / period)
    upper.push(m + mult * std)
    lower.push(m - mult * std)
  }
  return { upper, mid, lower }
}

export function macd(
  values: number[],
  fast = 12,
  slow = 26,
  signal = 9,
): { dif: (number | null)[]; dea: (number | null)[]; hist: (number | null)[] } {
  const emaFast = ema(values, fast)
  const emaSlow = ema(values, slow)
  const dif: (number | null)[] = values.map((_, i) => {
    const f = emaFast[i]
    const s = emaSlow[i]
    return f != null && s != null ? f - s : null
  })
  const difNums = dif.map((v) => v ?? 0)
  const dea = ema(difNums, signal)
  const hist = dif.map((d, i) => {
    const de = dea[i]
    return d != null && de != null ? (d - de) * 2 : null
  })
  return { dif, dea, hist }
}

export function kdj(
  high: number[],
  low: number[],
  close: number[],
  n = 9,
  kPeriod = 3,
  dPeriod = 3,
): { k: (number | null)[]; d: (number | null)[]; j: (number | null)[] } {
  const rsv: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    if (i < n - 1) {
      rsv.push(null)
      continue
    }
    let hh = -Infinity
    let ll = Infinity
    for (let j = i - n + 1; j <= i; j++) {
      hh = Math.max(hh, high[j])
      ll = Math.min(ll, low[j])
    }
    rsv.push(hh === ll ? 50 : ((close[i] - ll) / (hh - ll)) * 100)
  }
  const k: (number | null)[] = []
  const d: (number | null)[] = []
  const j: (number | null)[] = []
  let pk = 50
  let pd = 50
  for (let i = 0; i < rsv.length; i++) {
    const r = rsv[i]
    if (r === null) {
      k.push(null)
      d.push(null)
      j.push(null)
      continue
    }
    pk = (pk * (kPeriod - 1) + r) / kPeriod
    pd = (pd * (dPeriod - 1) + pk) / dPeriod
    k.push(pk)
    d.push(pd)
    j.push(3 * pk - 2 * pd)
  }
  return { k, d, j }
}

export function wr(high: number[], low: number[], close: number[], period = 14): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    let hh = -Infinity
    let ll = Infinity
    for (let j = i - period + 1; j <= i; j++) {
      hh = Math.max(hh, high[j])
      ll = Math.min(ll, low[j])
    }
    const r = hh === ll ? -50 : ((hh - close[i]) / (hh - ll)) * -100
    out.push(r)
  }
  return out
}

export function cci(high: number[], low: number[], close: number[], period = 20): (number | null)[] {
  const tp = close.map((c, i) => (high[i] + low[i] + c) / 3)
  const out: (number | null)[] = []
  for (let i = 0; i < tp.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    const slice = tp.slice(i - period + 1, i + 1)
    const mean = slice.reduce((a, b) => a + b, 0) / period
    const md = slice.reduce((a, b) => a + Math.abs(b - mean), 0) / period
    out.push(md === 0 ? 0 : (tp[i] - mean) / (0.015 * md))
  }
  return out
}

export function bias(close: number[], period = 6): (number | null)[] {
  const ma = sma(close, period)
  return close.map((c, i) => {
    const m = ma[i]
    return m != null && m !== 0 ? ((c - m) / m) * 100 : null
  })
}

export function obv(close: number[], volume: number[]): (number | null)[] {
  const out: (number | null)[] = []
  let acc = 0
  for (let i = 0; i < close.length; i++) {
    if (i === 0) {
      out.push(null)
      acc = volume[i]
      continue
    }
    if (close[i] > close[i - 1]) acc += volume[i]
    else if (close[i] < close[i - 1]) acc -= volume[i]
    out.push(acc)
  }
  return out
}

export function rsi(values: number[], period = 14): (number | null)[] {
  const out: (number | null)[] = []
  let avgGain = 0
  let avgLoss = 0
  for (let i = 0; i < values.length; i++) {
    if (i === 0) {
      out.push(null)
      continue
    }
    const ch = values[i] - values[i - 1]
    const gain = ch > 0 ? ch : 0
    const loss = ch < 0 ? -ch : 0
    if (i < period) {
      avgGain += gain
      avgLoss += loss
      out.push(null)
      if (i === period - 1) {
        avgGain /= period
        avgLoss /= period
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
        out[i] = 100 - 100 / (1 + rs)
      }
      continue
    }
    avgGain = (avgGain * (period - 1) + gain) / period
    avgLoss = (avgLoss * (period - 1) + loss) / period
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss
    out.push(100 - 100 / (1 + rs))
  }
  return out
}

/** DMI：+DI / -DI / ADX(14)。 */
export function dmi(
  high: number[],
  low: number[],
  close: number[],
  period = 14,
): { pdi: (number | null)[]; mdi: (number | null)[]; adx: (number | null)[] } {
  const len = close.length
  const pdm: number[] = []
  const mdm: number[] = []
  const tr: number[] = []
  for (let i = 0; i < len; i++) {
    if (i === 0) {
      pdm.push(0)
      mdm.push(0)
      tr.push(high[i] - low[i])
      continue
    }
    const up = high[i] - high[i - 1]
    const down = low[i - 1] - low[i]
    pdm.push(up > down && up > 0 ? up : 0)
    mdm.push(down > up && down > 0 ? down : 0)
    tr.push(
      Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1])),
    )
  }
  const smooth = (arr: number[]): number[] => {
    const s: number[] = new Array(len).fill(0)
    let sum = 0
    for (let i = 0; i < period; i++) sum += arr[i]
    s[period - 1] = sum
    for (let i = period; i < len; i++) {
      s[i] = s[i - 1] - s[i - 1] / period + arr[i]
    }
    return s
  }
  const trs = smooth(tr)
  const pdms = smooth(pdm)
  const mdms = smooth(mdm)
  const pdi: (number | null)[] = []
  const mdi: (number | null)[] = []
  const dx: (number | null)[] = []
  for (let i = 0; i < len; i++) {
    if (i < period - 1 || trs[i] === 0) {
      pdi.push(null)
      mdi.push(null)
      dx.push(null)
      continue
    }
    const plus = (100 * pdms[i]) / trs[i]
    const minus = (100 * mdms[i]) / trs[i]
    pdi.push(plus)
    mdi.push(minus)
    const sum = plus + minus
    dx.push(sum === 0 ? 0 : (100 * Math.abs(plus - minus)) / sum)
  }
  const adx: (number | null)[] = []
  let adxSeed = 0
  let adxCount = 0
  for (let i = 0; i < len; i++) {
    const d = dx[i]
    if (d === null) {
      adx.push(null)
      continue
    }
    if (adxCount < period) {
      adxSeed += d
      adxCount++
      adx.push(adxCount === period ? adxSeed / period : null)
      continue
    }
    const prev = adx[i - 1] ?? d
    adx.push((prev * (period - 1) + d) / period)
  }
  return { pdi, mdi, adx }
}

/** DMA：DDD=MA(short)-MA(long)，AMA=MA(DDD)。 */
export function dma(
  close: number[],
  short = 10,
  long = 50,
  signal = 10,
): { ddd: (number | null)[]; ama: (number | null)[] } {
  const maS = sma(close, short)
  const maL = sma(close, long)
  const ddd = close.map((_, i) => {
    const s = maS[i]
    const l = maL[i]
    return s != null && l != null ? s - l : null
  })
  const dddNums = ddd.map((v) => v ?? 0)
  const ama = sma(dddNums, signal)
  return { ddd, ama }
}

/** TRIX(12) 及其信号线。 */
export function trix(close: number[], period = 12): { trix: (number | null)[]; signal: (number | null)[] } {
  const e1 = ema(close, period)
  const e1n = e1.map((v) => v ?? 0)
  const e2 = ema(e1n, period)
  const e2n = e2.map((v) => v ?? 0)
  const e3 = ema(e2n, period)
  const trixLine: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    if (i === 0 || e3[i] === null || e3[i - 1] === null || e3[i - 1] === 0) {
      trixLine.push(null)
      continue
    }
    trixLine.push(((e3[i]! - e3[i - 1]!) / e3[i - 1]!) * 100)
  }
  const trixNums = trixLine.map((v) => v ?? 0)
  const signal = sma(trixNums, 9)
  return { trix: trixLine, signal }
}

/** 成交量比率 VR(26)。 */
export function vr(close: number[], volume: number[], period = 26): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    if (i < period) {
      out.push(null)
      continue
    }
    let up = 0
    let down = 0
    let flat = 0
    for (let j = i - period + 1; j <= i; j++) {
      if (close[j] > close[j - 1]) up += volume[j]
      else if (close[j] < close[j - 1]) down += volume[j]
      else flat += volume[j]
    }
    const den = down + flat / 2
    out.push(den === 0 ? 100 : ((up + flat / 2) / den) * 100)
  }
  return out
}

/** 简易 EMV(14)。 */
export function emv(high: number[], low: number[], volume: number[], period = 14): (number | null)[] {
  const raw: (number | null)[] = []
  for (let i = 0; i < high.length; i++) {
    if (i === 0) {
      raw.push(null)
      continue
    }
    const mid = (high[i] + low[i]) / 2
    const prevMid = (high[i - 1] + low[i - 1]) / 2
    const range = high[i] - low[i]
    const box = range === 0 ? 0 : volume[i] / range
    raw.push(box === 0 ? 0 : (mid - prevMid) / box)
  }
  const nums = raw.map((v) => v ?? 0)
  return sma(nums, period)
}

/** ROC(12) 变动率。 */
export function roc(close: number[], period = 12): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    if (i < period) {
      out.push(null)
      continue
    }
    const base = close[i - period]
    out.push(base === 0 ? 0 : ((close[i] - base) / base) * 100)
  }
  return out
}

/** MTM(12) 动量。 */
export function mtm(close: number[], period = 12): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    out.push(i < period ? null : close[i] - close[i - period])
  }
  return out
}

/** PSY(12) 心理线。 */
export function psy(close: number[], period = 12): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < close.length; i++) {
    if (i < period) {
      out.push(null)
      continue
    }
    let up = 0
    for (let j = i - period + 1; j <= i; j++) {
      if (close[j] > close[j - 1]) up++
    }
    out.push((up / period) * 100)
  }
  return out
}

/** 抛物线 SAR。 */
export function sar(high: number[], low: number[], step = 0.02, maxStep = 0.2): (number | null)[] {
  const len = high.length
  const out: (number | null)[] = new Array(len).fill(null)
  if (len < 2) return out

  let bull = true
  let af = step
  let ep = high[0]
  let sarVal = low[0]
  out[0] = sarVal

  for (let i = 1; i < len; i++) {
    sarVal = sarVal + af * (ep - sarVal)
    if (bull) {
      if (low[i] < sarVal) {
        bull = false
        sarVal = ep
        ep = low[i]
        af = step
      } else {
        if (high[i] > ep) {
          ep = high[i]
          af = Math.min(af + step, maxStep)
        }
        sarVal = Math.min(sarVal, low[i - 1], i > 1 ? low[i - 2] : low[i - 1])
      }
    } else if (high[i] > sarVal) {
      bull = true
      sarVal = ep
      ep = high[i]
      af = step
    } else {
      if (low[i] < ep) {
        ep = low[i]
        af = Math.min(af + step, maxStep)
      }
      sarVal = Math.max(sarVal, high[i - 1], i > 1 ? high[i - 2] : high[i - 1])
    }
    out[i] = sarVal
  }
  return out
}
