<template>
  <div class="page-shell">
    <el-space direction="vertical" fill style="width: 100%">
      <game-status :status="store.gameStatus" :round="store.currentRound" />
      <el-card shadow="never">
        <template #header>开局前设置</template>
        <el-alert
          title="当前默认场景为 6 人暗牌场，AI API 配置仅作用于本房间，开局前可随时保存。"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />
        <el-form label-width="120px">
          <el-form-item label="场景预设">
            <el-space>
              <el-tag type="success">{{ settingsForm.scene.name }}</el-tag>
              <el-tag type="info">{{ settingsForm.scene.preset }}</el-tag>
            </el-space>
          </el-form-item>
          <el-form-item label="场景说明">
            <el-input v-model="settingsForm.scene.description" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="玩家人数">
            <el-input-number v-model="settingsForm.scene.playerCount" :min="6" :max="6" :disabled="true" />
          </el-form-item>
          <el-divider content-position="left">AI 接口配置</el-divider>
          <el-form-item label="API Base URL">
            <el-input v-model="settingsForm.ai.baseUrl" placeholder="例如 https://api.openai.com/v1" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="settingsForm.ai.apiKey" type="password" show-password placeholder="仅本房间使用" />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="settingsForm.ai.model" placeholder="例如 gpt-4o-mini" />
          </el-form-item>
          <el-form-item label="超时时间(秒)">
            <el-input-number v-model="settingsForm.ai.timeoutSeconds" :min="1" :step="1" />
          </el-form-item>
          <el-form-item label="温度">
            <el-input-number v-model="settingsForm.ai.temperature" :min="0" :max="2" :step="0.1" />
          </el-form-item>
          <el-form-item label="启用模拟模式">
            <el-switch v-model="settingsForm.ai.enableMock" />
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="primary" :loading="settingsLoading" @click="saveSettings">保存设置</el-button>
              <el-button :disabled="settingsLoading" @click="resetSettings">重置当前配置</el-button>
              <el-tag :type="store.roomSettings.ai.hasApiKey ? 'success' : 'warning'">
                {{ store.roomSettings.ai.hasApiKey ? '已配置 API Key' : '未配置 API Key' }}
              </el-tag>
            </el-space>
          </el-form-item>
        </el-form>
      </el-card>
      <player-list :players="store.players" />
      <el-card>
        <template #header>房间 {{ gameId }}</template>
        <p>{{ store.started ? '对局已开始，正在等待进入对局页。' : '等待玩家加入，或直接开局由系统按 6 人场补足 AI。' }}</p>
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
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { getRoom, startGame, updateRoomSettings } from '@/api/gameApi';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useGameStore } from '@/store/modules/gameStore';
import type { RoomSettingsForm, RoomSettings } from '@/types/game';

const props = defineProps<{ gameId: string }>();
const store = useGameStore();
const router = useRouter();
const loading = ref(false);
const settingsLoading = ref(false);
const { connect, disconnect, isConnected } = useGameSocket();

function cloneSettings(settings: RoomSettings): RoomSettingsForm {
  return {
    scene: {
      preset: settings.scene.preset,
      name: settings.scene.name,
      description: settings.scene.description,
      playerCount: settings.scene.playerCount,
    },
    ai: {
      baseUrl: settings.ai.baseUrl,
      apiKey: '',
      model: settings.ai.model,
      timeoutSeconds: settings.ai.timeoutSeconds,
      temperature: settings.ai.temperature,
      enableMock: settings.ai.enableMock,
    },
  };
}

const settingsForm = reactive<RoomSettingsForm>(cloneSettings(store.roomSettings));

watch(
  () => store.roomSettings,
  (settings) => {
    const next = cloneSettings(settings);
    Object.assign(settingsForm.scene, next.scene);
    Object.assign(settingsForm.ai, next.ai);
  },
  { immediate: true, deep: true },
);

const goGame = async () => {
  await router.push({ name: 'game', params: { gameId: props.gameId } });
};

const refreshRoom = async () => {
  loading.value = true;
  try {
    const snapshot = await getRoom(props.gameId, store.myId);
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

const saveSettings = async () => {
  settingsLoading.value = true;
  try {
    const snapshot = await updateRoomSettings(props.gameId, settingsForm);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
    ElMessage.success('设置已保存');
  } catch {
    ElMessage.error('保存设置失败');
  } finally {
    settingsLoading.value = false;
  }
};

const resetSettings = () => {
  const next = cloneSettings(store.roomSettings);
  Object.assign(settingsForm.scene, next.scene);
  Object.assign(settingsForm.ai, next.ai);
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
