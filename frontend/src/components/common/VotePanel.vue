<template>
  <el-card shadow="never" class="vote-panel" :class="{ 'is-active': !disabled }">
    <template #header>
      <div class="panel-header">
        <span>✋ 投票阶段</span>
      </div>
    </template>
    
    <div class="panel-content">
      <el-alert
        v-if="!disabled"
        title="请在圆桌上点击玩家头像进行投票，或选择弃票"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else
        title="等待其他人投票..."
        type="info"
        :closable="false"
        show-icon
      />
    </div>

    <div class="vote-actions">
      <el-button type="info" plain :disabled="disabled" @click="handleAbstain" style="width: 100%">
        放弃投票 (弃票)
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { Player } from '@/types/game';

const props = defineProps<{
  players: Player[];
  disabled?: boolean;
  currentPlayerId?: string;
}>();

const emit = defineEmits<{
  submit: [targetId: string];
}>();

const handleAbstain = () => {
  if (props.disabled) return;
  emit('submit', 'abstain');
};
</script>

<style scoped>
.vote-panel {
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
}
.vote-panel.is-active {
  border-color: var(--accent-color);
  box-shadow: 0 0 10px rgba(var(--accent-color-rgb), 0.2);
}
.panel-header {
  font-weight: bold;
  color: var(--text-primary);
}
.panel-content {
  margin-bottom: 12px;
}
.vote-actions {
  display: flex;
  justify-content: center;
}
</style>
