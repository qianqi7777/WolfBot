<template>
  <!-- 双列竖排玩家座位 -->
  <div class="player-grid">
    <!-- 左列 -->
    <div class="player-column left-column">
      <PlayerSeat
        v-for="seat in leftColumn"
        :key="seat.player.id"
        :player="seat.player"
        :is-speaking="seat.player.id === currentSpeakerId"
        :is-self="seat.player.id === myId"
        :seat-index="seat.index"
        :total-seats="allPlayers.length"
        layout="vertical"
        @seat-click="(id: string) => $emit('seat-click', id)"
      />
    </div>
    <!-- 中央区域 -->
    <div class="center-area">
      <slot />
    </div>
    <!-- 右列 -->
    <div class="player-column right-column">
      <PlayerSeat
        v-for="seat in rightColumn"
        :key="seat.player.id"
        :player="seat.player"
        :is-speaking="seat.player.id === currentSpeakerId"
        :is-self="seat.player.id === myId"
        :seat-index="seat.index"
        :total-seats="allPlayers.length"
        layout="vertical"
        @seat-click="(id: string) => $emit('seat-click', id)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { Player } from '@/types/game';
import PlayerSeat from './PlayerSeat.vue';

const props = defineProps<{
  /** 所有玩家 */
  players: Player[];
  /** 当前发言者 ID */
  currentSpeakerId: string | null;
  /** 自己的 ID */
  myId: string;
}>();

defineEmits<{
  /** 点击座位事件 */
  'seat-click': [playerId: string];
}>();

/** 过滤观战者并按座位号排序 */
const allPlayers = computed(() => {
  return props.players
    .filter((p) => !p.isSpectator)
    .sort((a, b) => a.seatNumber - b.seatNumber);
});

/** 分成左右两列 */
const leftColumn = computed(() => {
  const players = allPlayers.value;
  const mid = Math.ceil(players.length / 2);
  return players.slice(0, mid).map((player, index) => ({ player, index }));
});

const rightColumn = computed(() => {
  const players = allPlayers.value;
  const mid = Math.ceil(players.length / 2);
  return players.slice(mid).map((player, index) => ({ player, index: mid + index }));
});
</script>

<style scoped>
.player-grid {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  gap: 24px;
  padding: 16px;
  min-height: 360px;
}

.player-column {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 140px;
}

.center-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 200px;
  padding: 16px;
}
</style>
