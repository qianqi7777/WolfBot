<template>
  <div class="table-container" ref="containerRef">
    <div :class="['player-grid', layoutMode]">
      <!-- 环形布局时，只有一个大容器，所有玩家绝对定位 -->
      <template v-if="layoutMode === 'circle'">
        <div class="circle-center">
          <slot />
        </div>
        <PlayerSeat
          v-for="(player, index) in allPlayers"
          :key="player.id"
          :player="player"
          :is-speaking="player.id === currentSpeakerId"
          :is-self="player.id === myId"
          :seat-index="index"
          :total-seats="allPlayers.length"
          :layout="'circle'"
          :container-width="containerSize.width"
          :container-height="containerSize.height"
          :is-wolf-teammate="wolfTeammates?.includes(player.seatNumber)"
          :targeted-by-wolves="wolfTargetUpdates?.filter(u => u.targetSeat === player.seatNumber)"
          @seat-click="(id: string) => $emit('seat-click', id)"
        />
      </template>

      <!-- 移动端两列竖排布局 -->
      <template v-else>
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
            :is-wolf-teammate="wolfTeammates?.includes(seat.player.seatNumber)"
            :targeted-by-wolves="wolfTargetUpdates?.filter(u => u.targetSeat === seat.player.seatNumber)"
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
            :is-wolf-teammate="wolfTeammates?.includes(seat.player.seatNumber)"
            :targeted-by-wolves="wolfTargetUpdates?.filter(u => u.targetSeat === seat.player.seatNumber)"
            @seat-click="(id: string) => $emit('seat-click', id)"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';

import type { Player } from '@/types/game';
import PlayerSeat from './PlayerSeat.vue';

const props = defineProps<{
  /** 所有玩家 */
  players: Player[];
  /** 当前发言者 ID */
  currentSpeakerId: string | null;
  /** 自己的 ID */
  myId: string;
  wolfTeammates?: number[];
  wolfTargetUpdates?: { wolfId: string; wolfSeat: number; targetSeat: number }[];
}>();

defineEmits<{
  /** 点击座位事件 */
  'seat-click': [playerId: string];
}>();

const containerRef = ref<HTMLElement | null>(null);
const containerSize = ref({ width: 600, height: 400 });
const layoutMode = ref<'circle' | 'vertical'>('circle');

/** 过滤观战者并按座位号排序 */
const allPlayers = computed(() => {
  return props.players
    .filter((p) => !p.isSpectator)
    .sort((a, b) => a.seatNumber - b.seatNumber);
});

/** 分成左右两列 (仅在 vertical 模式下使用) */
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

let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (containerRef.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        containerSize.value = { width, height };
        // 阈值设为 768px (iPad 宽度左右)
        if (width < 768) {
          layoutMode.value = 'vertical';
        } else {
          layoutMode.value = 'circle';
        }
      }
    });
    resizeObserver.observe(containerRef.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
});
</script>

<style scoped>
.table-container {
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  position: relative;
  min-height: 450px;
}

.player-grid {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
}

.player-grid.vertical {
  justify-content: center;
  align-items: flex-start;
  gap: 24px;
  padding: 16px;
}

.player-grid.circle {
  justify-content: center;
  align-items: center;
}

.circle-center {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0) 70%);
  z-index: 0;
}

/* Vertical 模式的样式 */
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
  z-index: 0;
}
</style>
