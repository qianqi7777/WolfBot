<template>
  <el-card shadow="never">
    <template #header>玩家列表</template>
    <el-space wrap>
      <el-tag
        v-for="player in players"
        :key="player.id"
        :type="player.isAlive ? 'success' : 'info'"
      >
        <span v-if="player.isSheriff" class="sheriff-badge">🏅</span>
        {{ player.seatNumber }}号({{ player.name }})
      </el-tag>
    </el-space>
  </el-card>
</template>

<script setup lang="ts">
import type { Player } from '@/types/game';

defineProps<{ players: Player[] }>();
</script>

<style scoped>
.sheriff-badge {
  margin-right: 2px;
}
</style>
