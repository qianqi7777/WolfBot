<template>
  <el-card shadow="never">
    <template #header>投票面板</template>
    <el-radio-group v-model="selected">
      <el-radio-button v-for="player in votablePlayers" :key="player.id" :label="player.id">
        {{ player.name }}
      </el-radio-button>
    </el-radio-group>
    <div class="actions">
      <el-button type="danger" :disabled="disabled || !selected" @click="handleVote">投票</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { Player } from '@/types/game';

const props = defineProps<{
  players: Player[];
  disabled?: boolean;
  currentPlayerId?: string;
}>();

const emit = defineEmits<{
  submit: [targetId: string];
}>();

const selected = defineModel<string>('selected', { default: '' });

const votablePlayers = computed(() =>
  props.players.filter((p) => p.id !== props.currentPlayerId),
);

const handleVote = () => {
  if (props.disabled || !selected.value) return;
  emit('submit', selected.value);
  selected.value = '';
};
</script>
