<template>
  <el-card shadow="never">
    <template #header>当前阶段</template>
    <strong>{{ label }}</strong>
    <span v-if="round > 0" class="round-label">第 {{ round }} 轮</span>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { GameStatus } from '@/types/game';
import { GAME_STATUS_LABELS } from '@/utils/constants';

const props = defineProps<{ status: GameStatus; round?: number }>();

const label = computed(() => GAME_STATUS_LABELS[props.status]);
const round = computed(() => props.round ?? 1);
</script>
