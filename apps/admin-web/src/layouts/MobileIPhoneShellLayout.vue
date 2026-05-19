<script setup lang="ts">
/** iPhone 17 Pro 预览壳：显示区域按 Apple 公布的物理分辨率换算为逻辑点（pt），1 CSS px ≈ 1 pt。 */
</script>

<template>
  <div class="shell-wrap">
    <p class="shell-hint">
      移动端 H5 预览区（触控优先）。显示区域为
      <strong>402×874 pt</strong>（由官方
      <a
        href="https://www.apple.com/iphone-17-pro/specs/"
        target="_blank"
        rel="noopener noreferrer"
      >2622×1206 像素显示屏</a
      >
      ÷ @3x 得到）；Dynamic Island 与 Home Indicator 叠在内容上，与真机一致。
    </p>
    <div class="device-frame" aria-label="iPhone 17 Pro 预览框">
      <div class="device-bezel">
        <div class="device-display">
          <div class="dynamic-island" aria-hidden="true" />
          <div class="screen-inner">
            <div class="screen-inner-stack">
              <div class="screen-scroll">
                <RouterView />
              </div>
              <!-- H5 模态层挂点：须留在壳内，避免 Teleport 到 body 铺满整页 -->
              <div id="h5-shell-portal" class="h5-shell-portal" />
            </div>
          </div>
          <div class="home-indicator" aria-hidden="true" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/**
 * iPhone 17 Pro（Apple 技术规格，非国行页亦可同参）
 * - 物理分辨率：1206 × 2622 像素（竖屏宽 × 高），460 ppi
 * - 逻辑分辨率（@3x）：402 × 874 pt
 * 见：https://www.apple.com/iphone-17-pro/specs/
 */
.shell-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 8px 0 24px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}
.shell-hint {
  margin: 0;
  max-width: 36rem;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
  text-align: center;
}
.shell-hint a {
  color: #2563eb;
  text-decoration: none;
}
.shell-hint a:hover {
  text-decoration: underline;
}
.device-frame {
  flex-shrink: 0;
  padding: 12px;
  background: linear-gradient(160deg, #2d3748 0%, #1a202c 100%);
  border-radius: 48px;
  box-shadow:
    0 24px 48px rgba(15, 23, 42, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.device-bezel {
  border-radius: 44px;
  padding: 3px;
  background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
}
.device-display {
  position: relative;
  /* 与 Apple 公布的竖屏逻辑尺寸一致：宽 402pt × 高 874pt */
  width: 402px;
  height: 874px;
  border-radius: 41px;
  overflow: hidden;
  background: #000;
}
.dynamic-island {
  position: absolute;
  top: 11px;
  left: 50%;
  transform: translateX(-50%);
  width: 126px;
  height: 37px;
  background: #000;
  border-radius: 20px;
  z-index: 2;
  pointer-events: none;
}
.screen-inner {
  position: relative;
  box-sizing: border-box;
  width: 402px;
  height: 874px;
  overflow: hidden;
  background: #fff;
}
.screen-inner-stack {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  position: relative;
}
.screen-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}
.h5-shell-portal {
  position: absolute;
  inset: 0;
  z-index: 80;
  pointer-events: none;
}
.home-indicator {
  position: absolute;
  bottom: 9px;
  left: 50%;
  transform: translateX(-50%);
  width: 134px;
  height: 5px;
  background: rgba(255, 255, 255, 0.35);
  border-radius: 100px;
  z-index: 2;
  pointer-events: none;
}
</style>
