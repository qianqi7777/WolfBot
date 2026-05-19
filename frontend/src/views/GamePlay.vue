<template>
  <div class="page-shell game-grid">
    <GameStatus :status="store.gameStatus" />
    <PlayerList :players="store.players" />
    <RoleCard :role="store.myRole" />
    <Announce :announcements="store.announceList" />
    <ChatBox :messages="store.chatList" @submit="submitSpeak" />
    <VotePanel :players="store.alivePlayers" @submit="submitVote" />
  </div>
</template>

<script setup lang="ts">
import Announce from '@/components/common/Announce.vue';
import ChatBox from '@/components/common/ChatBox.vue';
import RoleCard from '@/components/common/RoleCard.vue';
import VotePanel from '@/components/common/VotePanel.vue';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { submitSpeak as apiSpeak, submitVote as apiVote } from '@/api/gameApi';
import { useGameStore } from '@/store/modules/gameStore';

const store = useGameStore();

const submitSpeak = async (content: string) => {
  await apiSpeak(store.gameId, content);
};

const submitVote = async (targetId: string) => {
  await apiVote(store.gameId, targetId);
};
</script>
