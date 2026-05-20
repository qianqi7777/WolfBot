<template>
  <el-card shadow="never">
    <template #header>座位选择</template>
    <div class="seat-grid">
      <div
        v-for="seat in seatList"
        :key="seat.number"
        class="seat-item"
        :class="{
          'seat-occupied': seat.player && seat.player.id !== myId,
          'seat-mine': seat.player && seat.player.id === myId,
          'seat-empty': !seat.player,
        }"
        @click="handleSeatClick(seat)"
      >
        <div class="seat-number">{{ seat.number }}号</div>
        <div v-if="seat.player" class="seat-name">
          {{ seat.player.name }}
        </div>
        <div v-else class="seat-empty-label">空位 — 点击入座</div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { Player } from '@/types/game';

const props = defineProps<{
  players: Player[];
  playerCount: number;
  myId: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  'select-seat': [seatNumber: number];
}>();

const seatList = computed(() => {
  const occupied = new Map<number, Player>();
  for (const p of props.players) {
    if (p.seatNumber > 0) occupied.set(p.seatNumber, p);
  }
  return Array.from({ length: props.playerCount }, (_, i) => ({
    number: i + 1,
    player: occupied.get(i + 1) ?? null,
  }));
});

const handleSeatClick = (seat: { number: number; player: Player | null }) => {
  if (props.disabled) return;
  if (!seat.player) {
    emit('select-seat', seat.number);
  }
};
</script>

<style scoped>
.seat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}
.seat-item {
  border: 2px solid #dcdfe6;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  transition: all 0.2s;
}
.seat-empty {
  border-style: dashed;
  border-color: #409eff;
  cursor: pointer;
}
.seat-empty:hover {
  background: #ecf5ff;
  border-color: #79bbff;
}
.seat-mine {
  border-color: #67c23a;
  background: #f0f9eb;
  cursor: default;
}
.seat-occupied {
  cursor: default;
  background: #fafafa;
}
.seat-number {
  font-weight: bold;
  font-size: 16px;
}
.seat-name {
  font-size: 13px;
  color: #606266;
  margin-top: 4px;
}
.seat-empty-label {
  font-size: 12px;
  color: #409eff;
  margin-top: 4px;
}
</style>
