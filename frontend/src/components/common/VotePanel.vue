<template>
  <el-card shadow="never">
    <template #header>投票面板</template>
    <el-radio-group v-model="selected">
      <el-radio-button v-for="player in players" :key="player.id" :label="player.id">
        {{ player.name }}
      </el-radio-button>
    </el-radio-group>
    <div class="actions">
      <el-button type="danger" :disabled="!selected" @click="$emit('submit', selected)">投票</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { Player } from '@/types/game';

defineProps<{ players: Player[] }>();

defineEmits<{
  submit: [targetId: string];
}>();

const selected = defineModel<string>('selected', { default: '' });
</script>
