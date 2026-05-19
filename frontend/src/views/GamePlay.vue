<template>
  <div class="page-shell game-grid">
    <GameStatus :status="store.gameStatus" :round="store.currentRound" />
    <PlayerList :players="store.players" />
    <RoleCard :role="store.myRole" />
    <Announce :announcements="store.announceList" />
    <ChatBox v-model:draft="speakDraft" :messages="store.chatList" @submit="submitSpeak" />
    <VotePanel v-model:selected="selectedTargetId" :players="store.alivePlayers" @submit="submitVote" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';

import { getGame, submitSpeak as apiSpeak, submitVote as apiVote } from '@/api/gameApi';
import Announce from '@/components/common/Announce.vue';
import ChatBox from '@/components/common/ChatBox.vue';
import RoleCard from '@/components/common/RoleCard.vue';
import VotePanel from '@/components/common/VotePanel.vue';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { useGameLogic } from '@/hooks/useGameLogic';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useGameStore } from '@/store/modules/gameStore';
import type { Player } from '@/types/game';

const props = defineProps<{ gameId: string }>();
const store = useGameStore();
const router = useRouter();
const speakDraft = ref('');
const selectedTargetId = ref('');
const { connect, disconnect } = useGameSocket();
const { canPlayerSpeak, canPlayerVote, isValidSpeak } = useGameLogic();

const selfPlayer = computed<Player | null>(() => store.selfPlayer);

const ensureGame = async () => {
  if (store.gameId !== props.gameId) {
    const snapshot = await getGame(props.gameId);
    store.applySnapshot(snapshot, store.myId || snapshot.playerId);
  }
  connect(props.gameId, store.myId);
};

const submitSpeak = async (content: string) => {
  if (!isValidSpeak(content)) {
    ElMessage.warning('发言内容无效');
    return;
  }
  if (!canPlayerSpeak(store.gameStatus, selfPlayer.value ?? undefined)) {
    ElMessage.warning('当前阶段不能发言');
    return;
  }
  await apiSpeak(store.gameId, store.myId, content);
  speakDraft.value = '';
};

const submitVote = async (targetId: string) => {
  if (!canPlayerVote(store.gameStatus, selfPlayer.value ?? undefined)) {
    ElMessage.warning('当前阶段不能投票');
    return;
  }
  if (!targetId) {
    ElMessage.warning('请选择投票目标');
    return;
  }
  await apiVote(store.gameId, store.myId, targetId);
  selectedTargetId.value = '';
};

onMounted(ensureGame);
watch(
  () => store.gameStatus,
  (status) => {
    if (status === 'end') {
      router.replace({ name: 'result', params: { gameId: props.gameId } });
    }
  },
  { immediate: true },
);
onBeforeUnmount(disconnect);
</script>
