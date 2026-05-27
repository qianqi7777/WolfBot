<template>
  <!--
    全屏翻牌弹窗：背面 → 0.8s 3D 翻转 → 正面（立绘大牌）
    遵守 prefers-reduced-motion / 用户动画开关：禁用时退化为淡入
  -->
  <Teleport to="body">
    <Transition name="reveal-fade">
      <div
        v-if="current"
        class="reveal-overlay"
        :class="{ 'mode-private': current.mode === 'private', 'mode-public': current.mode === 'public' }"
        @click="handleOverlayClick"
      >
        <div class="reveal-stage" @click.stop>
          <!-- 标题 -->
          <div class="reveal-title">
            <span class="title-text">{{ titleText }}</span>
            <span v-if="current.name" class="target-name">{{ current.name }}</span>
          </div>

          <!-- 3D 翻牌容器 -->
          <div
            class="card"
            :class="{ flipped: flipped, 'no-motion': !animationsEffective }"
          >
            <div class="card-inner">
              <!-- 牌背 -->
              <div class="card-face card-back">
                <img v-if="cardBackUrl" :src="cardBackUrl" alt="牌背" />
                <div v-else class="css-card-back">
                  <div class="logo-mark">狼</div>
                </div>
              </div>
              <!-- 牌正面 -->
              <div class="card-face card-front">
                <RoleCardBig :role="current.role" />
              </div>
            </div>
          </div>

          <!-- 操作提示 -->
          <div class="reveal-hint">点击空白处或等待自动关闭</div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue';

import { useRoleReveal } from '@/hooks/useRoleReveal';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { getCardBack } from '@/utils/cardImage';
import RoleCardBig from './RoleCardBig.vue';

const { current, dismissCurrent } = useRoleReveal();
const { animationsEffective } = useUserPreferences();

const flipped = ref(false);
const cardBackUrl = computed(() => getCardBack());

const titleText = computed(() => {
  if (!current.value) return '';
  if (current.value.title) return current.value.title;
  return current.value.mode === 'private' ? '你的身份' : '身份揭晓';
});

let flipTimer: ReturnType<typeof setTimeout> | null = null;
let closeTimer: ReturnType<typeof setTimeout> | null = null;

function clearTimers(): void {
  if (flipTimer) {
    clearTimeout(flipTimer);
    flipTimer = null;
  }
  if (closeTimer) {
    clearTimeout(closeTimer);
    closeTimer = null;
  }
}

function close(): void {
  clearTimers();
  flipped.value = false;
  dismissCurrent();
}

function handleOverlayClick(): void {
  close();
}

// 监听队首变化：新请求进来时触发翻牌
watch(current, (req) => {
  clearTimers();
  if (!req) {
    flipped.value = false;
    return;
  }
  flipped.value = false;
  const flipDelay = animationsEffective.value ? 200 : 0;
  flipTimer = setTimeout(() => {
    flipped.value = true;
  }, flipDelay);

  const autoMs = req.autoCloseMs ?? 3500;
  if (autoMs > 0) {
    closeTimer = setTimeout(close, autoMs);
  }
});

onUnmounted(clearTimers);
</script>

<style scoped>
/* 遮罩 */
.reveal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  cursor: pointer;
}

.reveal-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  cursor: default;
  max-width: 90vw;
}

.reveal-title {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.9);
}

.title-text {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.target-name {
  font-size: 16px;
  opacity: 0.85;
}

/* 3D 翻牌（来源：3dtransforms.desandro.com/card-flip） */
.card {
  perspective: 1000px;
  width: min(280px, 70vw);
  aspect-ratio: 2 / 3;
}

.card-inner {
  position: relative;
  width: 100%;
  height: 100%;
  transition: transform 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
}

.card.flipped .card-inner {
  transform: rotateY(180deg);
}

/* 禁用动画：直接显示正面 */
.card.no-motion .card-inner {
  transition: none;
}

.card-face {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border-radius: 12px;
  overflow: hidden;
}

.card-back {
  z-index: 2;
}

.card-front {
  transform: rotateY(180deg);
}

.card-back img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 缺少 card-back.webp 时的 CSS 牌背 */
.css-card-back {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #1f2937, #0f172a);
  border: 2px solid #4b5563;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-mark {
  font-size: 64px;
  font-weight: 800;
  color: #fbbf24;
  text-shadow: 0 4px 16px rgba(251, 191, 36, 0.4);
  letter-spacing: 0.1em;
}

.reveal-hint {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.7);
  user-select: none;
}

/* 弹窗本身的淡入淡出 */
.reveal-fade-enter-active,
.reveal-fade-leave-active {
  transition: opacity 0.25s ease;
}
.reveal-fade-enter-from,
.reveal-fade-leave-to {
  opacity: 0;
}

/* 尊重 prefers-reduced-motion：关闭所有动画 */
@media (prefers-reduced-motion: reduce) {
  .card-inner {
    transition: none !important;
  }
  .reveal-fade-enter-active,
  .reveal-fade-leave-active {
    transition: none !important;
  }
}

@media (max-width: 768px) {
  .title-text { font-size: 18px; }
  .target-name { font-size: 14px; }
}
</style>
