<template>
  <div class="page-shell">
    <el-space direction="vertical" fill style="width: 100%">
      <game-status :status="store.gameStatus" :round="store.currentRound" />
      <el-card shadow="never">
        <template #header>开局前设置</template>
        <el-alert
          title="选择场景预设后自动填充配置，AI API 配置仅作用于本房间，开局前可随时保存。"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />
        <el-form label-width="120px">
          <el-form-item label="场景预设">
            <el-select v-model="settingsForm.scene.preset" placeholder="选择场景" @change="onPresetChange">
              <el-option
                v-for="opt in SCENE_PRESET_OPTIONS"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              >
                <span>{{ opt.label }}</span>
                <span style="float: right; color: #8492a6; font-size: 12px">{{ opt.playerCount }}人</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="场景说明">
            <el-input v-model="settingsForm.scene.description" type="textarea" :rows="2" />
          </el-form-item>
          <el-form-item label="玩家人数">
            <el-input-number v-model="settingsForm.scene.playerCount" :min="6" :max="12" disabled />
          </el-form-item>
          <el-form-item label="每人发言时间(秒)">
            <el-input-number v-model="settingsForm.scene.speakTimeoutSeconds" :min="5" :max="120" :step="5" />
            <span style="margin-left: 8px; color: #909399; font-size: 12px">每人轮流发言的超时时间</span>
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
              <el-button :loading="testLoading" @click="testConnection">测试连通性</el-button>
              <el-button :disabled="settingsLoading" @click="resetSettings">重置当前配置</el-button>
              <el-tag :type="store.roomSettings.ai.hasApiKey ? 'success' : 'warning'">
                {{ store.roomSettings.ai.hasApiKey ? '已配置 API Key' : '未配置 API Key' }}
              </el-tag>
              <el-tag :type="settingsForm.ai.enableMock ? 'warning' : 'success'">
                {{ settingsForm.ai.enableMock ? '当前为模拟模式' : '当前为真实接口模式' }}
              </el-tag>
            </el-space>
          </el-form-item>
          <el-alert
            v-if="connectionResult"
            :title="connectionResult.message"
            :type="connectionResult.success ? 'success' : 'error'"
            show-icon
            :closable="false"
            style="margin-top: 12px"
          />
          <el-alert
            v-if="connectionResult?.success && settingsForm.ai.enableMock"
            title="真实接口已连通，但当前仍启用模拟模式，对局不会调用该接口。"
            type="warning"
            show-icon
            :closable="false"
            style="margin-top: 12px"
          />
        </el-form>
      </el-card>
      <!-- 座位选择 -->
      <SeatMap
        :players="store.players"
        :player-count="settingsForm.scene.playerCount"
        :my-id="store.myId"
        :disabled="store.started"
        @select-seat="handleSeatSelect"
      />
      <el-card>
        <template #header>房间 {{ gameId }}</template>
        <p>{{ store.started ? '对局已开始，正在等待进入对局页。' : '选择座位后等待房主开始对局，或由房主直接开始。' }}</p>
        <el-space>
          <el-button type="primary" @click="goGame">进入对局页</el-button>
          <el-button
            v-if="!store.started && store.isOwner"
            type="success"
            :loading="loading"
            @click="startRoom"
          >
            开始对局
          </el-button>
          <el-tag v-if="!store.started && !store.isOwner" type="info">
            等待房主开始对局...
          </el-tag>
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
import { isAxiosError } from 'axios';

import { changeSeat, getRoom, startGame, testRoomAiConnection, updateRoomSettings } from '@/api/gameApi';
import GameStatus from '@/components/game/GameStatus.vue';
import SeatMap from '@/components/game/SeatMap.vue';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useGameStore, saveAiConfigToLocal, getSavedAiConfig } from '@/store/modules/gameStore';
import { SCENE_PRESET_OPTIONS } from '@/utils/constants';
import type { AiConnectionTestResult, RoomSettingsForm, RoomSettings } from '@/types/game';

const props = defineProps<{ gameId: string }>();
const store = useGameStore();
const router = useRouter();
const loading = ref(false);
const settingsLoading = ref(false);
const testLoading = ref(false);
const connectionResult = ref<AiConnectionTestResult | null>(null);
const { connect, disconnect, isConnected } = useGameSocket();

function cloneSettings(settings: RoomSettings): RoomSettingsForm {
  // 优先使用 localStorage 中保存的非敏感字段
  const saved = getSavedAiConfig();
  return {
    scene: {
      preset: settings.scene.preset,
      name: settings.scene.name,
      description: settings.scene.description,
      playerCount: settings.scene.playerCount,
      speakTimeoutSeconds: settings.scene.speakTimeoutSeconds,
    },
    ai: {
      baseUrl: saved.baseUrl || settings.ai.baseUrl,
      apiKey: '',
      model: saved.model || settings.ai.model,
      timeoutSeconds: saved.timeoutSeconds || settings.ai.timeoutSeconds,
      temperature: saved.temperature ?? settings.ai.temperature,
      enableMock: saved.enableMock ?? settings.ai.enableMock,
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

watch(
  settingsForm,
  () => {
    connectionResult.value = null;
  },
  { deep: true },
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

const handleSeatSelect = async (seatNumber: number) => {
  try {
    const snapshot = await changeSeat(props.gameId, store.myId, seatNumber);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
  } catch {
    ElMessage.error('换座失败，座位可能已被占用');
  }
};

const startRoom = async () => {
  loading.value = true;
  try {
    // 开局前自动保存设置，确保API Key等配置已提交到后端
    try {
      const settingsSnapshot = await updateRoomSettings(props.gameId, settingsForm);
      store.applySnapshot(settingsSnapshot, store.myId || settingsSnapshot.playerId);
      saveAiConfigToLocal(settingsForm.ai);
    } catch {
      // 设置保存失败不阻塞开局，但提示用户
      ElMessage.warning('设置保存失败，将使用上次保存的配置开局');
    }
    const snapshot = await startGame(props.gameId, store.myId);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
    await router.replace({ name: 'game', params: { gameId: props.gameId } });
  } catch (error) {
    const msg = isAxiosError(error) ? String(error.response?.data?.detail ?? '开局失败') : '开局失败';
    ElMessage.error(msg);
  } finally {
    loading.value = false;
  }
};

const saveSettings = async () => {
  settingsLoading.value = true;
  try {
    const snapshot = await updateRoomSettings(props.gameId, settingsForm);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
    // 持久化 AI 配置到 localStorage（不含 apiKey）
    saveAiConfigToLocal(settingsForm.ai);
    ElMessage.success('设置已保存');
  } catch {
    ElMessage.error('保存设置失败');
  } finally {
    settingsLoading.value = false;
  }
};

const testConnection = async () => {
  testLoading.value = true;
  try {
    connectionResult.value = await testRoomAiConnection(props.gameId, settingsForm.ai);
    if (connectionResult.value.success) {
      ElMessage.success('连通性测试成功');
    }
  } catch (error) {
    connectionResult.value = null;
    ElMessage.error(
      isAxiosError(error)
        ? String(error.response?.data?.detail ?? error.response?.data?.message ?? '连通性测试失败')
        : '连通性测试失败',
    );
  } finally {
    testLoading.value = false;
  }
};

const resetSettings = () => {
  const next = cloneSettings(store.roomSettings);
  Object.assign(settingsForm.scene, next.scene);
  Object.assign(settingsForm.ai, next.ai);
};

const onPresetChange = (preset: string) => {
  const opt = SCENE_PRESET_OPTIONS.find((o) => o.value === preset);
  if (opt) {
    settingsForm.scene.name = opt.label;
    settingsForm.scene.description = opt.description;
    settingsForm.scene.playerCount = opt.playerCount;
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
