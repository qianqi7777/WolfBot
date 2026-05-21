<template>
  <!-- 单条聊天气泡组件 -->
  <div
    class="chat-bubble-wrapper"
    :class="{
      'is-self': isSelfMessage,
      'is-other': !isSelfMessage && !message.isAI,
      'is-ai': !isSelfMessage && message.isAI,
    }"
  >
    <!-- 头像（非自己消息时显示在左侧，自己消息显示在右侧） -->
    <img
      v-if="!isSelfMessage"
      :src="senderAvatar"
      :alt="message.playerName"
      class="bubble-avatar"
    />

    <!-- 气泡内容 -->
    <div class="bubble-content">
      <!-- 名字 + 时间 -->
      <div class="bubble-header">
        <span class="bubble-name">{{ message.playerName }}</span>
        <span v-if="message.isAI" class="bubble-ai-badge">AI</span>
        <span class="bubble-time">{{ message.time }}</span>
      </div>
      <!-- 消息正文 -->
      <div class="bubble-body">
        {{ message.content }}
      </div>
    </div>

    <!-- 自己的头像（右侧） -->
    <img
      v-if="isSelfMessage"
      :src="senderAvatar"
      :alt="message.playerName"
      class="bubble-avatar"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { ChatMessage, Player } from '@/types/game';
import { getPlayerAvatar } from '@/utils/avatar';
import avatarHuman from '@/assets/avatars/avatar-human.svg';
import avatarAI from '@/assets/avatars/avatar-ai.svg';

const props = defineProps<{
  /** 消息数据 */
  message: ChatMessage;
  /** 自己的 ID（区分自己/他人） */
  myId: string;
  /** 发送者玩家数据（用于头像，可能为 undefined） */
  player: Player | undefined;
}>();

/** 是否是自己发送的消息 */
const isSelfMessage = computed(() => props.message.playerId === props.myId);

/** 发送者头像 URL */
const senderAvatar = computed(() => {
  if (props.player) {
    return getPlayerAvatar(props.player);
  }
  // 降级：无玩家数据时根据 isAI 选择默认头像
  return props.message.isAI ? avatarAI : avatarHuman;
});
</script>

<style scoped>
.chat-bubble-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
  animation: fadeIn 0.3s ease;
}

/* 自己的消息：靠右对齐 */
.is-self {
  flex-direction: row-reverse;
}

/* 头像缩略图 */
.bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
}

/* 气泡内容区 */
.bubble-content {
  max-width: 70%;
  min-width: 60px;
}

/* 名字 + 时间行 */
.bubble-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 2px;
  font-size: 11px;
  color: var(--text-secondary);
}

/* 自己的消息名字行靠右 */
.is-self .bubble-header {
  flex-direction: row-reverse;
}

.bubble-name {
  font-weight: 500;
}

.bubble-ai-badge {
  font-size: 9px;
  color: #8b5cf6;
  background: var(--bg-bubble-ai, rgba(139, 92, 246, 0.2));
  padding: 0 3px;
  border-radius: 2px;
  line-height: 1.4;
}

.bubble-time {
  font-size: 10px;
  opacity: 0.7;
}

/* 气泡正文 */
.bubble-body {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

/* 他人消息：靠左/灰色气泡 */
.is-other .bubble-body {
  background: var(--bg-bubble-other);
  color: var(--text-bubble-other);
  border-top-left-radius: 4px;
}

/* AI 消息：靠左/紫色气泡 */
.is-ai .bubble-body {
  background: var(--bg-bubble-ai);
  color: var(--text-bubble-other);
  border-top-left-radius: 4px;
}

/* 自己消息：靠右/主色调气泡 */
.is-self .bubble-body {
  background: var(--bg-bubble-self);
  color: var(--text-bubble-self);
  border-top-right-radius: 4px;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
