<template>
  <div class="page-shell">
    <el-row :gutter="16">
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>创建游戏</template>
          <el-input v-model="playerName" placeholder="玩家名称" />
          <div class="actions">
            <el-button type="primary" :loading="loading" @click="handleCreate">创建并进入</el-button>
          </div>
        </el-card>
      </el-col>
      <el-col :md="12" :sm="24">
        <el-card>
          <template #header>加入游戏</template>
          <el-input v-model="gameId" placeholder="房间号" />
          <el-input v-model="playerName" placeholder="玩家名称" style="margin-top: 12px" />
          <div class="actions">
            <el-button :loading="loading" @click="handleJoin">加入房间</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { createGame, joinGame } from '@/api/gameApi';
import { useGameStore } from '@/store/modules/gameStore';

const router = useRouter();
const store = useGameStore();
const gameId = ref('');
const playerName = ref('玩家');
const loading = ref(false);

const enterRoom = async (snapshot: Awaited<ReturnType<typeof createGame>>) => {
  store.initGame(snapshot.gameId, snapshot.playerId, snapshot.players);
  store.setMyRole(snapshot.myRole);
  store.setGameStatus(snapshot.gameStatus);
  await router.push({ name: 'room', params: { gameId: snapshot.gameId } });
};

const handleCreate = async () => {
  loading.value = true;
  try {
    await enterRoom(await createGame(playerName.value));
  } catch {
    ElMessage.error('创建游戏失败');
  } finally {
    loading.value = false;
  }
};

const handleJoin = async () => {
  if (!gameId.value.trim()) {
    ElMessage.warning('请输入房间号');
    return;
  }
  loading.value = true;
  try {
    await enterRoom(await joinGame(gameId.value, playerName.value));
  } catch {
    ElMessage.error('加入游戏失败');
  } finally {
    loading.value = false;
  }
};
</script>
