<template>
  <el-card class="sheriff-election-card" shadow="always">
    <template #header>
      <div class="sheriff-header">
        <span>警长竞选</span>
        <el-tag v-if="electionPhase === 'campaign'" type="warning" size="small">上警阶段</el-tag>
        <el-tag v-else-if="electionPhase === 'speech'" type="info" size="small">竞选发言</el-tag>
        <el-tag v-else-if="electionPhase === 'vote'" type="success" size="small">投票选举</el-tag>
        <el-tag v-else-if="electionPhase === 'result'" type="primary" size="small">竞选结果</el-tag>
      </div>
    </template>

    <!-- 上警阶段 -->
    <div v-if="electionPhase === 'campaign'" class="election-phase">
      <p class="phase-desc">选择是否上警参加警长竞选</p>
      <div class="campaign-actions">
        <el-button
          v-if="!isCandidate && isAlive"
          type="warning"
          @click="handleCampaign('run')"
        >
          上警竞选
        </el-button>
        <el-button
          v-if="isCandidate"
          type="info"
          @click="handleCampaign('withdraw')"
        >
          退选
        </el-button>
      </div>
      <div v-if="candidateNames.length" class="candidate-list">
        <p>已上警玩家：</p>
        <el-tag
          v-for="name in candidateNames"
          :key="name"
          type="warning"
          effect="plain"
          class="candidate-tag"
        >
          {{ name }}
        </el-tag>
      </div>
    </div>

    <!-- 竞选发言阶段 -->
    <div v-else-if="electionPhase === 'speech'" class="election-phase">
      <p v-if="currentSpeakerName" class="phase-desc">
        轮到 <strong>{{ currentSpeakerName }}</strong> 竞选发言
      </p>
      <div v-if="isCurrentSpeaker" class="speech-actions">
        <ChatBox
          :messages="[]"
          :disabled="false"
          @submit="handleCampaignSpeech"
        />
      </div>
      <div v-else class="waiting-hint">
        <el-alert type="info" :closable="false" description="等待候选人发言..." />
      </div>
    </div>

    <!-- 投票选举阶段 -->
    <div v-else-if="electionPhase === 'vote'" class="election-phase">
      <p class="phase-desc">请投票选举警长（非候选人才能投票）</p>
      <div v-if="isCandidate" class="waiting-hint">
        <el-alert type="info" :closable="false" description="你是候选人，不能投票" />
      </div>
      <div v-else-if="!isAlive" class="waiting-hint">
        <el-alert type="info" :closable="false" description="你已死亡，不能投票" />
      </div>
      <div v-else class="vote-grid">
        <el-button
          v-for="candidate in candidatePlayers"
          :key="candidate.id"
          :type="votedFor === candidate.id ? 'success' : 'default'"
          @click="handleVote(candidate.id)"
          class="vote-btn"
        >
          {{ candidate.seatNumber }}号({{ candidate.name }})
        </el-button>
        <el-button type="info" @click="handleVote('abstain')" class="vote-btn">
          弃权
        </el-button>
      </div>
    </div>

    <!-- 竞选结果 -->
    <div v-else-if="electionPhase === 'result'" class="election-phase">
      <el-result
        v-if="sheriffResult && sheriffResult.sheriffId"
        icon="success"
        :title="sheriffResult.message"
      />
      <el-result
        v-else
        icon="info"
        :title="sheriffResult?.message || '本局无警长'"
      />
    </div>

    <!-- 警长转让（死亡时选择继承人） -->
    <div v-if="sheriffTransferNeedsChoice" class="transfer-section">
      <el-divider />
      <p class="phase-desc">你是警长，请选择继承人转让徽章</p>
      <div class="vote-grid">
        <el-button
          v-for="player in transferCandidates"
          :key="player.id"
          type="warning"
          @click="handleTransfer(player.id)"
          class="vote-btn"
        >
          {{ player.seatNumber }}号({{ player.name }})
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import ChatBox from './ChatBox.vue';
import { useGameStore } from '@/store/modules/gameStore';
import { useGameSocket } from '@/hooks/useGameSocket';

const store = useGameStore();
const { send } = useGameSocket();

// 竞选阶段判断
const electionPhase = computed(() => {
  if (store.sheriffElectResult) return 'result';
  if (store.sheriffVoteStart) return 'vote';
  if (store.sheriffSpeechTurn) return 'speech';
  if (store.sheriffElectStart) return 'campaign';
  return 'campaign';
});

const isAlive = computed(() => store.selfPlayer?.isAlive ?? false);
const isCandidate = computed(() => store.myId ? store.sheriffCandidateIds.includes(store.myId) : false);
const isCurrentSpeaker = computed(() =>
  store.sheriffSpeechTurn?.currentSpeakerId === store.myId
);
const currentSpeakerName = computed(() =>
  store.sheriffSpeechTurn?.currentSpeakerName || ''
);
const votedFor = computed(() => {
  // 检查是否已经投过票（从 announce 中判断）
  return '';
});

const candidateNames = computed(() => {
  return store.sheriffCandidateIds.map(id => {
    const p = store.players.find(p => p.id === id);
    return p ? `${p.seatNumber}号(${p.name})` : id;
  });
});

const candidatePlayers = computed(() => {
  return store.sheriffCandidateIds
    .map(id => store.players.find(p => p.id === id))
    .filter((p): p is NonNullable<typeof p> => p !== undefined);
});

const sheriffResult = computed(() => store.sheriffElectResult);

// 警长转让相关
const sheriffTransferNeedsChoice = computed(() =>
  store.sheriffTransfer?.needsChoice === true &&
  store.sheriffTransfer?.fromPlayerId === store.myId
);

const transferCandidates = computed(() => {
  if (!store.sheriffTransfer?.candidateIds) return [];
  return store.sheriffTransfer.candidateIds
    .map(id => store.players.find(p => p.id === id))
    .filter((p): p is NonNullable<typeof p> => p !== undefined && p.isAlive);
});

// 操作
function handleCampaign(action: 'run' | 'withdraw') {
  send({ type: 'sheriff_campaign', payload: { action } });
}

function handleCampaignSpeech(content: string) {
  // 竞选发言通过 speak 消息发送
  send({ type: 'speak', payload: { content } });
}

function handleVote(targetId: string) {
  send({ type: 'sheriff_vote', payload: { targetId } });
}

function handleTransfer(targetId: string) {
  send({ type: 'sheriff_transfer', payload: { targetId } });
}
</script>

<style scoped>
.sheriff-election-card {
  animation: fadeIn 0.3s ease;
}

.sheriff-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.election-phase {
  padding: 8px 0;
}

.phase-desc {
  margin-bottom: 12px;
  font-size: 14px;
}

.campaign-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.candidate-list {
  margin-top: 8px;
}

.candidate-list p {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 6px;
}

.candidate-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}

.vote-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.vote-btn {
  min-width: 100px;
}

.waiting-hint {
  margin-top: 8px;
}

.transfer-section {
  margin-top: 8px;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
