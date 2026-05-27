<template>
  <!-- 单个座位卡片：头像+名字+状态角标 -->
  <div
    class="player-seat"
    :class="{
      'is-speaking': isSpeaking,
      'is-self': isSelf,
      'is-dead': !player.isAlive,
      'is-targeted': targetedByWolves && targetedByWolves.length > 0
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
      <!-- 身份标识 (右上角) -->
      <div v-if="badgeInfo" class="badge-role" :class="badgeInfo.type" @click.stop="openRoleGuess">
        {{ badgeInfo.label }}
      </div>
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
    <div v-if="player.isSheriff" class="seat-sheriff-pill">警长</div>
    <!-- AI 标识 -->
    <div v-if="player.isAI" class="seat-ai-tag">AI</div>

    <!-- 被狼人袭击的标记圆圈 -->
    <div v-if="targetedByWolves && targetedByWolves.length" class="wolf-target-indicators">
      <div
        v-for="(wolf, idx) in targetedByWolves"
        :key="wolf.wolfId"
        class="wolf-target-circle"
        :style="getWolfIndicatorStyle(idx, targetedByWolves.length)"
        :title="`${wolf.wolfSeat}号狼人正在锁定`"
      >
        {{ wolf.wolfSeat }}
      </div>
    </div>

    <!-- 猜测身份弹窗 (点击标签后弹出) -->
    <el-popover
      v-model:visible="showRoleGuess"
      placement="top"
      width="160"
      trigger="click"
    >
      <div class="role-guess-menu">
        <p style="margin-top: 0; font-weight: bold; font-size: 12px; text-align: center;">标记猜测身份</p>
        <el-button size="small" type="danger" plain @click="setGuess('wolf')">🐺 狼人</el-button>
        <el-button size="small" type="success" plain @click="setGuess('civilian')">🧑‍🌾 平民</el-button>
        <el-button size="small" type="primary" plain @click="setGuess('prophet')">🔮 预言家</el-button>
        <el-button size="small" type="warning" plain @click="setGuess('witch')">🧙‍♀️ 女巫</el-button>
        <el-button size="small" type="info" plain @click="setGuess('guard')">🛡️ 守卫</el-button>
        <el-button size="small" type="info" plain @click="setGuess('hunter')">🔫 猎人</el-button>
        <el-button size="small" type="info" plain @click="setGuess('idiot')">🤍 白痴</el-button>
        <el-button size="small" @click="setGuess('')">清除标记</el-button>
      </div>
    </el-popover>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

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
  /** 容器宽度 (仅 circle 布局用) */
  containerWidth?: number;
  /** 容器高度 (仅 circle 布局用) */
  containerHeight?: number;
  /** 是否是狼人队友 */
  isWolfTeammate?: boolean;
  /** 被哪些狼人队友锁定 */
  targetedByWolves?: { wolfId: string; wolfSeat: number; targetSeat: number }[];
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

/** 身份猜测状态 (本地存储) */
const guessedRole = ref('');
const showRoleGuess = ref(false);

const openRoleGuess = () => {
  // 只有未确认真实身份的玩家，才能进行标记
  if (!props.isSelf) {
    showRoleGuess.value = true;
  }
};

const setGuess = (role: string) => {
  guessedRole.value = role;
  showRoleGuess.value = false;
};

const roleLabels: Record<string, string> = {
  wolf: '狼',
  civilian: '民',
  prophet: '预',
  witch: '女',
  guard: '守',
  hunter: '猎',
  idiot: '白痴',
};

/** 显示的身份标识：只展示公开信息、自己的身份或用户猜测，不直接泄露隐藏角色 */
const badgeInfo = computed(() => {
  if (props.isSelf) {
    if (props.player.role && props.player.role !== 'unknown' && roleLabels[props.player.role]) {
      return { label: roleLabels[props.player.role], type: 'self' };
    }
    return { label: '我', type: 'self' };
  }

  if (props.player.isSheriff) {
    return { label: '警长', type: 'sheriff' };
  }

  if (props.player.isIdiotRevealed) {
    return { label: '白痴', type: 'public' };
  }

  // 预言家查验结果仅暴露阵营（wolf / civilian），不显示具体角色
  if (props.player.revealedRole === 'wolf') {
    return { label: '狼', type: 'public' };
  }
  if (props.player.revealedRole === 'civilian') {
    return { label: '好', type: 'public' };
  }

  if (props.isWolfTeammate) {
    return { label: '狼', type: 'wolf' };
  }

  if (guessedRole.value && roleLabels[guessedRole.value]) {
    return { label: `?${roleLabels[guessedRole.value]}`, type: 'guess' };
  }

  return { label: '?', type: 'guess' };
});

const getWolfIndicatorStyle = (index: number, total: number) => {
  const angle = total === 1 ? -45 : -90 + (index / total) * 360;
  const radius = 50;
  const offsetX = Math.cos((angle * Math.PI) / 180) * radius;
  const offsetY = Math.sin((angle * Math.PI) / 180) * radius;

  return {
    transform: `translate(-50%, -50%) translate(${offsetX}px, ${offsetY}px)`,
  };
};

/** 座位定位样式 */
const seatStyle = computed(() => {
  // 竖排布局不需要绝对定位
  if (props.layout === 'vertical') {
    return {};
  }

  // 环形布局：通过计算相对于容器中心的位移，确保不会重叠并在正确的位置
  const total = Math.max(props.totalSeats, 1);
  // 座位0在正上方（270度/ -90度）
  const angleDeg = (props.seatIndex / total) * 360 - 90;
  const angleRad = (angleDeg * Math.PI) / 180;
  
  const w = props.containerWidth || 600;
  const h = props.containerHeight || 400;
  
  // 留出边距避免头像被截断，头像宽度约80px
  const padding = 60;
  const rx = (w / 2) - padding;
  const ry = (h / 2) - padding;

  // 如果 rx 或 ry 偏小，需要有最小值
  const finalRx = Math.max(rx, 120);
  const finalRy = Math.max(ry, 120);

  const x = finalRx * Math.cos(angleRad);
  const y = finalRy * Math.sin(angleRad);

  return {
    transform: `translate(${x}px, ${y}px)`,
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
  transition: filter 0.4s ease, opacity 0.4s ease;
  z-index: 1;
}

.player-seat:hover {
  z-index: 20;
}

.player-seat:hover .seat-avatar-wrapper {
  transform: scale(1.1);
}

/* 竖排布局 */
.player-seat[layout="vertical"] {
  position: relative;
  left: auto;
  top: auto;
  margin: 0;
  transform: none !important;
}

.player-seat.is-dead {
  filter: grayscale(100%) opacity(0.6);
}

.seat-avatar-wrapper {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.seat-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 3px solid var(--border-color);
  object-fit: cover;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

/* 身份标记 badge-role */
.badge-role {
  position: absolute;
  top: -4px;
  right: -4px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 2px 6px;
  font-size: 10px;
  font-weight: bold;
  z-index: 10;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.badge-role.guess {
  opacity: 0.8;
  cursor: pointer;
}
.badge-role.guess:hover {
  opacity: 1;
  background: var(--bg-hover);
}
.badge-role.confirmed {
  background: var(--accent-color);
  color: #fff;
  border-color: var(--accent-color);
}

.badge-role.self {
  background: #2563eb;
  color: #fff;
  border-color: #2563eb;
}

.badge-role.sheriff {
  background: #f59e0b;
  color: #111827;
  border-color: #f59e0b;
}

.badge-role.public {
  background: #6b7280;
  color: #fff;
  border-color: #6b7280;
}

.badge-role.wolf {
  background: #b91c1c;
  color: #fff;
  border-color: #b91c1c;
}

.role-guess-menu {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.role-guess-menu .el-button {
  margin-left: 0;
  justify-content: flex-start;
}

.seat-sheriff-pill {
  margin-top: 4px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  background: linear-gradient(135deg, #facc15, #f59e0b);
  color: #111827;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.35);
}

/* 自己的座位头像边框高亮 */
.is-self .seat-avatar {
  border-color: var(--accent-color);
}

/* 被狼人锁定的特效（刀机效果） */
.is-targeted .seat-avatar {
  border-color: var(--faction-wolf, #ef4444);
  box-shadow: 0 0 15px rgba(239, 68, 68, 0.8), inset 0 0 10px rgba(239, 68, 68, 0.5);
  animation: pulse-danger 1s infinite alternate;
}

@keyframes pulse-danger {
  0% { box-shadow: 0 0 10px rgba(239, 68, 68, 0.5); }
  100% { box-shadow: 0 0 25px rgba(239, 68, 68, 1); }
}

.wolf-target-indicators {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 0;
  height: 0;
  z-index: 15;
  pointer-events: none;
}

.wolf-target-circle {
  position: absolute;
  background-color: #2a2a2a;
  color: #ff4d4f;
  font-size: 11px;
  font-weight: bold;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #ff4d4f;
  border-radius: 50%;
  box-shadow: 0 0 8px rgba(255, 77, 79, 0.8);
  animation: float 2s infinite ease-in-out alternate;
}

@keyframes float {
  0% { transform: translateY(0); }
  100% { transform: translateY(-4px); }
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
