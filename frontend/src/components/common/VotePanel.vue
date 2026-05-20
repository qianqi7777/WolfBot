<template>
  <el-card shadow="never">
    <template #header>投票面板</template>
    <el-radio-group v-model="selected">
      <el-radio-button v-for="player in votablePlayers" :key="player.id" :value="player.id">
        {{ player.seatNumber }}号({{ player.name }})
      </el-radio-button>
    </el-radio-group>
    <div class="actions">
      <el-button type="danger" :disabled="disabled || !selected || selected === 'abstain'" @click="handleVote">投票</el-button>
      <el-button type="info" :disabled="disabled" @click="handleAbstain">弃票</el-button>
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
  if (props.disabled || !selected.value || selected.value === 'abstain') return;
  emit('submit', selected.value);
  selected.value = '';
};

const handleAbstain = () => {
  if (props.disabled) return;
  emit('submit', 'abstain');
  selected.value = '';
};
</script>
