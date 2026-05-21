<template>
  <!-- 单个座位卡片：头像+名字+状态角标 -->
  <div
    class="player-seat"
    :class="{
      'is-speaking': isSpeaking,
      'is-self': isSelf,
      'is-dead': !player.isAlive,
    }"
    :style="seatStyle"
    @click="$emit('seat-click', player.id)"
  >
    <!-- 头像区域 -->
    <div class="seat-avatar-wrapper">
      <!-- 警长角标 -->
      <img
        v-if="player.isSheriff"
        :src="sheriffBadgeUrl"
        class="badge badge-sheriff"
        alt="警长"
      />
      <!-- 头像 -->
      <img
        :src="avatarUrl"
        :alt="player.name"
        class="seat-avatar"
      />
      <!-- 座位号徽章 -->
      <span class="seat-number">{{ player.seatNumber }}</span>
      <!-- 死亡标记 -->
      <img
        v-if="!player.isAlive"
        :src="deadBadgeUrl"
        class="badge badge-dead"
        alt="已死亡"
      />
    </div>
    <!-- 名字 -->
    <div class="seat-name">{{ player.name }}</div>
    <!-- AI 标识 -->
    <div v-if="player.isAI" class="seat-ai-tag">AI</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { Player } from '@/types/game';
import { getPlayerAvatar } from '@/utils/avatar';
import badgeSheriff from '@/assets/avatars/badge-sheriff.svg';
import badgeDead from '@/assets/avatars/badge-dead.svg';

const props = defineProps<{
  /** 玩家数据 */
  player: Player;
  /** 是否当前发言者 */
  isSpeaking: boolean;
  /** 是否是自己 */
  isSelf: boolean;
  /** 在环形中的索引位置 */
  seatIndex: number;
  /** 总座位数 */
  totalSeats: number;
  /** 布局模式：circle(环形) / vertical(竖排) */
  layout?: 'circle' | 'vertical';
}>();

defineEmits<{
  'seat-click': [playerId: string];
}>();

/** 头像 URL */
const avatarUrl = computed(() => getPlayerAvatar(props.player));

/** 警长徽章 URL */
const sheriffBadgeUrl = badgeSheriff;

/** 死亡标记 URL */
const deadBadgeUrl = badgeDead;

/** 座位定位样式 */
const seatStyle = computed(() => {
  // 竖排布局不需要绝对定位
  if (props.layout === 'vertical') {
    return {};
  }

  // 环形布局：通过 CSS transform 定位到环形对应位置
  const total = Math.max(props.totalSeats, 1);
  const angleDeg = (props.seatIndex / total) * 360 + 90;
  const angleRad = (angleDeg * Math.PI) / 180;
  const rx = 42;
  const ry = 38;
  const x = rx * Math.cos(angleRad);
  const y = ry * Math.sin(angleRad);

  return {
    transform: `translate(${x}%, ${y}%)`,
  };
});
</script>

<style scoped>
.player-seat {
  position: absolute;
  left: 50%;
  top: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 80px;
  margin-left: -40px;
  margin-top: -40px;
  cursor: pointer;
  transition: filter 0.4s ease, opacity 0.4s ease, box-shadow 0.3s ease;
  z-index: 1;
}

/* 竖排布局 */
.player-seat[layout="vertical"] {
  position: relative;
  left: auto;
  top: auto;
  margin: 0;
}

.seat-avatar-wrapper {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}

.seat-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 3px solid var(--border-color);
  object-fit: cover;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

/* 自己的座位头像边框高亮 */
.is-self .seat-avatar {
  border-color: var(--accent-color);
}

/* 发言者脉冲动画 */
.is-speaking .seat-avatar {
  border-color: var(--accent-color);
  animation: pulse-glow 1.5s ease-in-out infinite;
}

@keyframes pulse-glow {
  0% {
    box-shadow: 0 0 0 0 var(--speaker-glow);
  }
  50% {
    box-shadow: 0 0 12px 4px var(--speaker-glow);
  }
  100% {
    box-shadow: 0 0 0 0 var(--speaker-glow);
  }
}

/* 死亡状态：灰度 + 半透明 */
.is-dead {
  filter: grayscale(1) opacity(0.5);
}

.is-dead .seat-avatar {
  border-color: #9ca3af;
}

/* 座位号徽章 */
.seat-number {
  position: absolute;
  left: -4px;
  bottom: -4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent-color);
  color: white;
  font-size: 11px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
}

/* 警长角标 */
.badge-sheriff {
  position: absolute;
  right: -6px;
  top: -6px;
  width: 20px;
  height: 20px;
  z-index: 3;
}

/* 死亡标记角标 */
.badge-dead {
  position: absolute;
  right: -4px;
  bottom: -4px;
  width: 20px;
  height: 20px;
  z-index: 3;
}

/* 名字 */
.seat-name {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-primary);
  text-align: center;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

/* AI 标识 */
.seat-ai-tag {
  font-size: 10px;
  color: #8b5cf6;
  background: var(--bg-bubble-ai, rgba(139, 92, 246, 0.2));
  padding: 0 4px;
  border-radius: 3px;
  margin-top: 1px;
  line-height: 1.4;
}
</style>
