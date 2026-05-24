<template>
  <!-- 聊天区域：气泡样式 + 头像 + 自己/AI/他人区分 -->
  <div class="chat-box-container">
    <!-- 消息列表 -->
    <div ref="chatBoxRef" class="chat-messages">
      <ChatBubble
        v-for="item in messages"
        :key="item.id"
        :message="item"
        :my-id="myId"
        :player="getPlayerById(item.playerId)"
      />
      <!-- 无消息占位 -->
      <div v-if="!messages.length" class="chat-empty">暂无发言记录</div>
    </div>
    <!-- 输入区域 -->
    <div class="chat-input-area">
      <el-input
        v-model="draft"
        type="textarea"
        :rows="2"
        placeholder="输入发言"
        :disabled="disabled"
        resize="none"
      />
      <el-button
        type="primary"
        :disabled="disabled || !draft.trim()"
        @click="handleSend"
      >
        发送
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

import type { ChatMessage, Player } from '@/types/game';
import ChatBubble from './ChatBubble.vue';

const props = defineProps<{
  /** 消息列表 */
  messages: ChatMessage[];
  /** 是否禁用输入 */
  disabled?: boolean;
  /** 自己的 ID */
  myId: string;
  /** 玩家列表（用于查找消息发送者信息） */
  players?: Player[];
}>();

const emit = defineEmits<{
  submit: [content: string];
}>();

const draft = defineModel<string>('draft', { default: '' });
const chatBoxRef = ref<HTMLElement | null>(null);

/** 根据 playerId 查找玩家数据 */
const getPlayerById = (playerId: string): Player | undefined => {
  return props.players?.find((p) => p.id === playerId);
};

/** 自动滚动到底部 */
const scrollToBottom = () => {
  nextTick(() => {
    if (chatBoxRef.value) {
      chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight;
    }
  });
};

// 消息列表变化时自动滚动
watch(() => props.messages.length, () => {
  scrollToBottom();
});

const handleSend = () => {
  if (props.disabled || !draft.value.trim()) return;
  emit('submit', draft.value);
  draft.value = '';
  scrollToBottom();
};
</script>

<style scoped>
.chat-box-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  min-height: 120px;
  max-height: 300px;
  scroll-behavior: smooth;
}

.chat-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 24px 0;
}

.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--border-color);
  align-items: flex-end;
  background: var(--bg-card-glass);
}

.chat-input-area .el-input {
  flex: 1;
}

.chat-input-area .el-button {
  flex-shrink: 0;
}
</style>
