<template>
  <!-- 玩家列表：使用 CircleTable + PlayerSeat 环形布局 -->
  <div class="player-list-circle">
    <CircleTable
      :players="players"
      :current-speaker-id="currentSpeakerId ?? null"
      :my-id="myId"
      @seat-click="(id: string) => $emit('seat-click', id)"
    >
      <!-- 中央 slot 内容由父组件传入 -->
      <slot />
    </CircleTable>
  </div>
</template>

<script setup lang="ts">
import type { Player } from '@/types/game';
import CircleTable from './CircleTable.vue';

defineProps<{
  /** 所有玩家 */
  players: Player[];
  /** 当前发言者 ID */
  currentSpeakerId?: string | null;
  /** 自己的 ID */
  myId: string;
}>();

defineEmits<{
  'seat-click': [playerId: string];
}>();
</script>

<style scoped>
.player-list-circle {
  width: 100%;
  height: 100%;
  min-height: 360px;
}
</style>
