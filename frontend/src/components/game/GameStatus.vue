<template>
  <div class="game-status-bar">
    <strong>{{ label }}</strong>
    <span v-if="round > 0" class="round-label">第 {{ round }} 轮</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { GameStatus } from '@/types/game';
import { GAME_STATUS_LABELS } from '@/utils/constants';

const props = defineProps<{ status: GameStatus; round?: number }>();

const label = computed(() => GAME_STATUS_LABELS[props.status]);
const round = computed(() => props.round ?? 1);
</script>

<style scoped>
.game-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-primary);
}
.round-label {
  color: var(--text-secondary, #6b7280);
  font-size: 12px;
}
</style>
