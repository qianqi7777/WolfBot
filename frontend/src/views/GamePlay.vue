<template>
  <div class="page-shell game-grid">
    <GameStatus :status="store.gameStatus" :round="store.currentRound" />
    <PlayerList :players="store.players" />
    <RoleCard :role="store.myRole" />
    <Announce :announcements="store.announceList" />
    <ChatBox
      :messages="store.chatList"
      :disabled="!canPlayerSpeak(store.gameStatus, selfPlayer ?? undefined)"
      @submit="submitSpeak"
    />
    <VotePanel
      :players="store.alivePlayers"
      :disabled="!canPlayerVote(store.gameStatus, selfPlayer ?? undefined)"
      :current-player-id="store.myId"
      @submit="submitVote"
    />
    <NightAction
      v-if="showNightAction"
      :role="store.myRole"
      :players="store.alivePlayers"
      :current-player-id="store.myId"
      :night-result="store.nightResult"
      @submit="submitNightActionHandler"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue';
import { useRouter } from 'vue-router';

import { submitSpeak as apiSpeak, submitVote as apiVote, submitNightAction as apiNightAction } from '@/api/gameApi';
import Announce from '@/components/common/Announce.vue';
import ChatBox from '@/components/common/ChatBox.vue';
import NightAction from '@/components/common/NightAction.vue';
import VotePanel from '@/components/common/VotePanel.vue';
import RoleCard from '@/components/common/RoleCard.vue';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { useGameLogic } from '@/hooks/useGameLogic';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useGameStore } from '@/store/modules/gameStore';

const store = useGameStore();
const { connect, disconnect } = useGameSocket();
const { canPlayerSpeak, canPlayerVote, canPlayerNightAction } = useGameLogic();
const router = useRouter();

const selfPlayer = computed(() => store.selfPlayer);

const showNightAction = computed(
  () => canPlayerNightAction(store.gameStatus, store.myRole, selfPlayer.value ?? undefined) && store.nightActionRequired,
);

const submitSpeak = async (content: string) => {
  await apiSpeak(store.gameId, store.myId, content);
};

const submitVote = async (targetId: string) => {
  await apiVote(store.gameId, store.myId, targetId);
};

const submitNightActionHandler = async (targetId: string) => {
  await apiNightAction(store.gameId, store.myId, targetId);
  store.setNightActionRequired(false);
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
