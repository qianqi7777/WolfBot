<template>
  <el-card shadow="never">
    <template #header>当前阶段</template>
    <strong>{{ label }}</strong>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { GameStatus } from '@/types/game';
import { GAME_STATUS_LABELS } from '@/utils/constants';

const props = defineProps<{ status: GameStatus }>();

const label = computed(() => GAME_STATUS_LABELS[props.status]);
</script>
