<template>
  <div class="page-shell">
    <el-space direction="vertical" fill style="width: 100%">
      <game-status :status="store.gameStatus" :round="store.currentRound" />
      <player-list :players="store.players" />
      <el-card>
        <template #header>房间 {{ gameId }}</template>
        <p>{{ store.started ? '对局已开始，正在等待进入对局页。' : '等待更多玩家加入并准备开局。' }}</p>
        <el-space>
          <el-button type="primary" @click="goGame">进入对局页</el-button>
          <el-button v-if="!store.started" type="success" :loading="loading" @click="startRoom">开始对局</el-button>
          <el-button :loading="loading" @click="refreshRoom">刷新房间</el-button>
          <el-tag :type="isConnected ? 'success' : 'warning'">
            {{ isConnected ? 'WebSocket 已连接' : 'WebSocket 未连接' }}
          </el-tag>
        </el-space>
      </el-card>
    </el-space>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { getRoom, startGame } from '@/api/gameApi';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useGameStore } from '@/store/modules/gameStore';

const props = defineProps<{ gameId: string }>();
const store = useGameStore();
const router = useRouter();
const loading = ref(false);
const { connect, disconnect, isConnected } = useGameSocket();

const goGame = async () => {
  await router.push({ name: 'game', params: { gameId: props.gameId } });
};

const refreshRoom = async () => {
  loading.value = true;
  try {
    const snapshot = await getRoom(props.gameId);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
  } catch {
    ElMessage.error('刷新房间失败');
  } finally {
    loading.value = false;
  }
};

const startRoom = async () => {
  loading.value = true;
  try {
    const snapshot = await startGame(props.gameId);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
    await router.replace({ name: 'game', params: { gameId: props.gameId } });
  } catch {
    ElMessage.error('开局失败');
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  if (store.gameId !== props.gameId) {
    await refreshRoom();
  }
  connect(props.gameId, store.myId);
});

watch(
  () => store.gameStatus,
  (status) => {
    if (status !== 'waiting') {
      router.replace({ name: 'game', params: { gameId: props.gameId } });
    }
  },
  { immediate: true },
);

onBeforeUnmount(disconnect);
</script>
