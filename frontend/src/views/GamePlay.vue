<template>
  <div class="page-shell game-layout">
    <!-- 左栏：操作区 -->
    <div class="game-left">
      <GameStatus :status="store.gameStatus" :round="store.currentRound" />
      <RoleCard :role="store.myRole" />
      <el-alert
        v-if="currentSpeakerName"
        :title="`轮到 ${currentSpeakerName} 发言`"
        type="info"
        show-icon
        :closable="false"
      />
      <ChatBox
        :messages="store.chatList"
        :disabled="!canPlayerSpeakNow"
        @submit="submitSpeak"
      />
      <VotePanel
        :players="store.alivePlayers"
        :disabled="!canPlayerVote(store.gameStatus, selfPlayer ?? undefined)"
        :current-player-id="store.myId"
        @submit="submitVote"
      />
<<<<<<< HEAD
      <!-- 投票结果明细展示 -->
      <el-card v-if="voteSummaryDisplay" class="vote-summary-card" shadow="always">
        <template #header>投票结果</template>
        <div class="vote-summary-content">
          <div v-for="item in voteSummaryDisplay" :key="item.targetSeat" class="vote-target-row">
            <div class="vote-target-header">
              <el-tag type="danger" effect="dark">{{ item.targetSeat }}号</el-tag>
              <span class="vote-count">{{ item.voterSeats.length }}票</span>
            </div>
            <div class="vote-voters">
              <el-tag
                v-for="seat in item.voterSeats"
                :key="seat"
                size="small"
                type="info"
                class="vote-voter-tag"
              >
                {{ seat }}号
              </el-tag>
            </div>
          </div>
        </div>
      </el-card>
=======
>>>>>>> d0960c3afea4069bbb61c2a39010d4d7eeeb5f6b
      <NightAction
        v-if="showNightAction"
        :role="store.myRole"
        :players="store.alivePlayers"
        :current-player-id="store.myId"
        :night-result="store.nightResult"
<<<<<<< HEAD
        :teammate-seats="store.wolfTeammates"
        @submit="submitNightActionHandler"
      />
      <!-- 预言家查验结果独立展示（NightAction提交后组件卸载，结果在此持续显示） -->
      <el-card v-if="prophetCheckDisplay" class="prophet-check-card" shadow="always">
        <template #header>查验结果</template>
        <el-alert
          :title="`${prophetCheckDisplay.seatLabel} 的身份是：${prophetCheckDisplay.roleLabel}`"
          :type="prophetCheckDisplay.role === 'wolf' ? 'error' : 'success'"
          show-icon
          :closable="false"
        />
      </el-card>
=======
        @submit="submitNightActionHandler"
      />
>>>>>>> d0960c3afea4069bbb61c2a39010d4d7eeeb5f6b
    </div>
    <!-- 右栏：信息流 -->
    <div class="game-right">
      <PlayerList :players="store.players" />
      <Announce :announcements="store.announceList" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { isAxiosError } from 'axios';

import { submitSpeak as apiSpeak, submitVote as apiVote, submitNightAction as apiNightAction } from '@/api/gameApi';
import Announce from '@/components/common/Announce.vue';
import ChatBox from '@/components/common/ChatBox.vue';
import NightAction from '@/components/common/NightAction.vue';
import VotePanel from '@/components/common/VotePanel.vue';
import RoleCard from '@/components/common/RoleCard.vue';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { ROLE_LABELS } from '@/utils/constants';
import { useGameLogic } from '@/hooks/useGameLogic';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useGameStore } from '@/store/modules/gameStore';

const store = useGameStore();
const { connect, disconnect } = useGameSocket();
const { canPlayerSpeak, canPlayerVote, canPlayerNightAction } = useGameLogic();
const router = useRouter();

const selfPlayer = computed(() => store.selfPlayer);
const currentSpeakerName = computed(() => {
  if (!store.currentSpeakerId) {
    return '';
  }
  const player = store.players.find((p) => p.id === store.currentSpeakerId);
  return player ? `${player.seatNumber}号` : '';
});

const canPlayerSpeakNow = computed(
  () =>
    canPlayerSpeak(store.gameStatus, selfPlayer.value ?? undefined) &&
    store.currentSpeakerId === store.myId,
);

const showNightAction = computed(
  () => canPlayerNightAction(store.gameStatus, store.myRole, selfPlayer.value ?? undefined) && store.nightActionRequired,
);

/** 预言家查验结果：在NightAction组件卸载后依然持续显示，直到进入下一轮夜晚 */
const prophetCheckDisplay = computed(() => {
  if (store.myRole !== 'prophet' || !store.nightResult?.checkedPlayerId) return null;
  const target = store.players.find((p) => p.id === store.nightResult!.checkedPlayerId);
  if (!target) return null;
  const checkedRole = store.nightResult.checkedRole ?? 'unknown';
  return {
    seatLabel: `${target.seatNumber}号`,
    role: checkedRole,
    roleLabel: ROLE_LABELS[checkedRole] ?? '未知',
  };
});

/** 投票结果汇总：按被投目标分组，显示谁投了谁 */
const voteSummaryDisplay = computed(() => {
  if (!store.voteSummary?.votes.length) return null;
  // 按 targetSeat 分组
  const grouped: Record<number, { targetSeat: number; voterSeats: number[] }> = {};
  for (const v of store.voteSummary.votes) {
    const tSeat = v.targetSeat ?? store.players.find((p) => p.id === v.targetId)?.seatNumber ?? 0;
    const vSeat = v.voterSeat ?? store.players.find((p) => p.id === v.voterId)?.seatNumber ?? 0;
    if (!grouped[tSeat]) {
      grouped[tSeat] = { targetSeat: tSeat, voterSeats: [] };
    }
    grouped[tSeat].voterSeats.push(vSeat);
  }
  // 按票数降序排列
  return Object.values(grouped).sort((a, b) => b.voterSeats.length - a.voterSeats.length);
});

const getErrorMessage = (error: unknown, fallback: string) => {
  if (isAxiosError(error)) {
    return String(error.response?.data?.detail ?? error.response?.data?.message ?? fallback);
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
};

const submitSpeak = async (content: string) => {
  try {
    await apiSpeak(store.gameId, store.myId, content);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '提交发言失败'));
  }
};

const submitVote = async (targetId: string) => {
  try {
    await apiVote(store.gameId, store.myId, targetId);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '提交投票失败'));
  }
};

const submitNightActionHandler = async (targetId: string) => {
  try {
    await apiNightAction(store.gameId, store.myId, targetId);
    store.setNightActionRequired(false);
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '提交夜间行动失败'));
  }
};

onMounted(() => {
  if (store.gameId && store.myId) {
    connect(store.gameId, store.myId);
  }
});

watch(
  () => store.gameStatus,
  (status) => {
    if (status === 'end') {
      router.replace({ name: 'result', params: { gameId: store.gameId } });
    }
  },
  { immediate: true },
);

onUnmounted(() => {
  disconnect();
});
</script>

<style scoped>
.game-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  align-items: start;
}

.game-left {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.game-right {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 24px;
  max-height: calc(100vh - 48px);
  overflow-y: auto;
}

<<<<<<< HEAD
.prophet-check-card {
  animation: fadeIn 0.3s ease;
}

.vote-summary-card {
  animation: fadeIn 0.3s ease;
}

.vote-summary-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.vote-target-row {
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.vote-target-row:last-child {
  border-bottom: none;
}

.vote-target-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.vote-count {
  color: var(--el-color-danger);
  font-weight: bold;
  font-size: 14px;
}

.vote-voters {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-left: 4px;
}

.vote-voter-tag {
  font-size: 12px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

=======
>>>>>>> d0960c3afea4069bbb61c2a39010d4d7eeeb5f6b
@media (max-width: 768px) {
  .game-layout {
    grid-template-columns: 1fr;
  }
  .game-right {
    position: static;
    max-height: none;
  }
}
</style>
