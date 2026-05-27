<template>
  <!-- 三段式布局：顶栏 + 中央圆桌 + 底部操作栏 + 暗色主题切换 -->
  <div
    class="game-play-shell"
    :data-theme="isNight ? 'dark' : 'light'"
  >
    <!-- 沉浸式背景层：底图（webp） + 现有 CSS 特效叠加 -->
    <div class="immersive-bg" :class="{ 'is-night': isNight }">
      <!-- 底图层（用户上传 bg-day/night.webp 后启用） -->
      <div
        v-if="enableBackground"
        class="bg-image-layer"
        :class="{ 'is-night': isNight }"
        :style="bgImageStyle"
      ></div>
      <!-- 原有 CSS 特效（星空 + 太阳/月亮）叠加在底图之上 -->
      <div class="stars"></div>
      <div class="moon-or-sun"></div>
    </div>

    <!-- 顶栏：GameStatus + CountdownTimer + RoleCard + SettingsMenu -->
    <div class="game-top-bar">
      <GameStatus :status="store.gameStatus" :round="store.currentRound" />
      <CountdownTimer
        :deadline="store.deadline"
        :total-seconds="currentPhaseTimeout"
      />
      <RoleCard :role="store.myRole" />
      <div class="top-bar-spacer"></div>
      <SettingsMenu />
    </div>

    <!-- 中央区域：圆桌 + 中央浮动内容 -->
    <div class="game-center">
      <PlayerList
        :players="store.players"
        :current-speaker-id="store.currentSpeakerId"
        :my-id="store.myId"
        :wolf-teammates="store.wolfTeammates"
        :wolf-target-updates="store.wolfTargetUpdates"
        @seat-click="handleSeatClick"
      >
        <!-- 中央浮动内容 -->
        <div class="center-content">
          <!-- 发言者提示 -->
          <div v-if="currentSpeakerName" class="speaker-hint animate-fade-in">
            <el-alert
              :title="`轮到 ${currentSpeakerName} 发言`"
              type="info"
              show-icon
              :closable="false"
            />
          </div>
          <!-- 系统公告 -->
          <Announce :announcements="store.announceList" />
        </div>
      </PlayerList>
    </div>

    <!-- 底部操作栏 -->
    <div class="game-bottom-bar">
      <!-- 聊天区域 -->
      <div class="chat-wrapper">
        <ChatBox
          :messages="store.chatList"
          :disabled="!canPlayerSpeakNow"
          :my-id="store.myId"
          :players="store.players"
          @submit="submitSpeak"
        />
      </div>

      <!-- 操作面板区域 -->
      <div class="action-panels">
        <!-- 投票面板 -->
        <VotePanel
          v-if="store.gameStatus === 'vote'"
          :players="store.alivePlayers"
          :disabled="!canPlayerVote(store.gameStatus, selfPlayer ?? undefined)"
          :current-player-id="store.myId"
          @submit="submitVote"
        />

        <!-- 狼人自爆按钮 -->
        <el-button
          v-if="canWolfSelfDestruct"
          type="danger"
          @click="handleWolfSelfDestruct"
          style="width: 100%"
        >
          💀 狼人自爆
        </el-button>

        <!-- 抢身份阶段 -->
        <RoleSelect v-if="store.gameStatus === 'role_select' && store.roleSelectStart" />

        <!-- 警长竞选阶段 -->
        <SheriffElection v-if="showSheriffElection" />

        <!-- 警长选择发言方向 -->
        <el-card v-if="showSpeakDirection" class="speak-direction-card" shadow="always">
          <template #header>
            <div class="speak-direction-header">
              <span>警长选择发言方向</span>
            </div>
          </template>
          <template v-if="isSheriffForDirection">
            <p class="phase-desc">请选择本轮发言的方向</p>
            <div class="speak-direction-actions">
              <el-button type="primary" @click="handleSpeakDirection('left')">
                ⬅ 逆时针（从左开始）
              </el-button>
              <el-button type="success" @click="handleSpeakDirection('right')">
                顺时针（从右开始）➡
              </el-button>
            </div>
          </template>
          <template v-else>
            <el-alert type="info" :closable="false" description="警长正在选择发言方向，请等待..." />
          </template>
        </el-card>

        <!-- 夜间行动 -->
        <NightAction
          v-if="showNightAction"
          :role="store.myRole"
          :players="store.alivePlayers"
          :current-player-id="store.myId"
          :night-result="store.nightResult"
          :prophet-check-result="store.prophetCheckResult"
          :teammate-seats="store.wolfTeammates"
          :wolf-target-updates="store.wolfTargetUpdates"
          :antidote-used="selfPlayer?.antidoteUsed"
          :poison-used="selfPlayer?.poisonUsed"
          :wolf-kill-target-id="store.wolfKillTargetId"
          :wolf-kill-target-label="store.wolfKillTargetLabel ?? undefined"
          @submit="submitNightActionHandler"
        />

        <!-- 预言家查验结果独立展示 -->
        <el-card v-if="prophetCheckDisplay" class="prophet-check-card" shadow="always">
          <template #header>查验结果</template>
          <el-alert
            :title="`${prophetCheckDisplay.seatLabel} 的身份是：${prophetCheckDisplay.roleLabel}`"
            :type="prophetCheckDisplay.role === 'wolf' ? 'error' : 'success'"
            show-icon
            :closable="false"
          />
        </el-card>
      </div>
    </div>

    <!-- 投票结果弹窗 -->
    <el-dialog
      v-model="showVoteSummaryDialog"
      title="🗳️ 投票结果揭晓"
      width="400px"
      center
      append-to-body
    >
      <div v-if="voteSummaryDisplay" class="vote-summary-content">
        <div v-for="item in voteSummaryDisplay.targets" :key="item.targetSeat" class="vote-target-row">
          <div class="vote-target-header">
            <el-tag type="danger" effect="dark">{{ item.targetSeat }}号({{ item.targetName }})</el-tag>
            <span class="vote-count">{{ item.voterSeats.length }}票</span>
          </div>
          <div class="vote-voters">
            <span style="font-size: 12px; color: var(--text-secondary); margin-right: 4px;">被投:</span>
            <el-tag
              v-for="(seat, idx) in item.voterSeats"
              :key="seat"
              size="small"
              type="info"
              class="vote-voter-tag"
            >
              {{ seat }}号({{ item.voterNames[idx] }})
            </el-tag>
          </div>
        </div>
        <!-- 弃票展示 -->
        <div v-if="voteSummaryDisplay.abstainVoters.length" class="vote-target-row abstain-row">
          <div class="vote-target-header">
            <el-tag type="info" effect="dark">弃票</el-tag>
            <span class="vote-count">{{ voteSummaryDisplay.abstainVoters.length }}人</span>
          </div>
          <div class="vote-voters">
            <el-tag
              v-for="av in voteSummaryDisplay.abstainVoters"
              :key="av.voterSeat"
              size="small"
              type="info"
              class="vote-voter-tag"
            >
              {{ av.voterSeat }}号({{ av.voterName }})
            </el-tag>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="showVoteSummaryDialog = false">确 定</el-button>
      </template>
    </el-dialog>

    <!-- 翻牌弹窗：全局唯一，由 useRoleReveal 队列触发 -->
    <RoleRevealModal />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { isAxiosError } from 'axios';

import { submitSpeak as apiSpeak, submitVote as apiVote, submitNightAction as apiNightAction } from '@/api/gameApi';
import Announce from '@/components/common/Announce.vue';
import ChatBox from '@/components/common/ChatBox.vue';
import CountdownTimer from '@/components/common/CountdownTimer.vue';
import NightAction from '@/components/common/NightAction.vue';
import RoleSelect from '@/components/common/RoleSelect.vue';
import SheriffElection from '@/components/common/SheriffElection.vue';
import VotePanel from '@/components/common/VotePanel.vue';
import RoleCard from '@/components/common/RoleCard.vue';
import RoleRevealModal from '@/components/common/RoleRevealModal.vue';
import SettingsMenu from '@/components/common/SettingsMenu.vue';
import GameStatus from '@/components/game/GameStatus.vue';
import PlayerList from '@/components/game/PlayerList.vue';
import { useGameLogic } from '@/hooks/useGameLogic';
import { useGameSocket } from '@/hooks/useGameSocket';
import { useRoleReveal } from '@/hooks/useRoleReveal';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { useGameStore } from '@/store/modules/gameStore';
import { getDesktopImageSet, getMobileImageSet } from '@/utils/backgroundImage';
import type { RoleType } from '@/types/game';

const store = useGameStore();
const { connect, disconnect, send } = useGameSocket();
const { canPlayerSpeak, canPlayerVote, canPlayerNightAction } = useGameLogic();
const { reveal, clear: clearReveal } = useRoleReveal();
const { enableBackground } = useUserPreferences();
const router = useRouter();

/** 是否是夜间（用于主题切换） */
const isNight = computed(() => store.gameStatus === 'night');

/** 背景底图 CSS（基于 enable 开关与当前阶段） */
const isMobile = ref(typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches);
if (typeof window !== 'undefined') {
  const mq = window.matchMedia('(max-width: 768px)');
  if (typeof mq.addEventListener === 'function') {
    mq.addEventListener('change', (e) => { isMobile.value = e.matches; });
  }
}
const bgImageStyle = computed(() => {
  const scene = isNight.value ? 'night' : 'day';
  const set = isMobile.value ? getMobileImageSet(scene) : getDesktopImageSet(scene);
  // image-set 不被识别时的兜底（旧 Safari 等）
  return set ? { backgroundImage: set } : {};
});

const selfPlayer = computed(() => store.selfPlayer);
const currentPhaseTimeout = computed(() => store.currentPhaseTimeout);
const showVoteSummaryDialog = ref(false);
const currentSpeakerName = computed(() => {
  if (!store.currentSpeakerId) {
    return '';
  }
  const player = store.players.find((p) => p.id === store.currentSpeakerId);
  return player ? `${player.seatNumber}号(${player.name})` : '';
});

const canPlayerSpeakNow = computed(
  () => {
    // 遗言模式：当前发言者是自己（允许死亡玩家）
    if (store.isLastWords && store.currentSpeakerId === store.myId) {
      return true;
    }
    // 正常发言模式
    return canPlayerSpeak(store.gameStatus, selfPlayer.value ?? undefined) &&
      store.currentSpeakerId === store.myId;
  },
);

const showNightAction = computed(
  () => canPlayerNightAction(store.gameStatus, store.myRole, selfPlayer.value ?? undefined) && store.nightActionRequired,
);

const showSheriffElection = computed(
  () => store.gameStatus === 'sheriff_election' &&
    (store.sheriffElectStart !== null || store.sheriffSpeechTurn !== null ||
     store.sheriffVoteStart !== null || store.sheriffElectResult !== null),
);

/** 是否显示狼人自爆按钮（发言/投票/竞选阶段均可自爆） */
const canWolfSelfDestruct = computed(
  () => store.myRole === 'wolf'
    && (store.gameStatus === 'speak' || store.gameStatus === 'vote' || store.gameStatus === 'sheriff_election')
    && selfPlayer.value?.isAlive === true
    && !store.wolfSelfDestructed,
);

/** 是否显示发言方向选择面板 */
const showSpeakDirection = computed(
  () => store.speakDirectionRequest !== null && store.gameStatus === 'speak',
);

/** 当前用户是否是负责选方向的警长 */
const isSheriffForDirection = computed(
  () => store.speakDirectionRequest?.sheriffId === store.myId,
);

/** 处理警长选择发言方向 */
const handleSpeakDirection = (direction: 'left' | 'right') => {
  send({ type: 'speak_direction', payload: { direction } });
  store.setSpeakDirectionRequest(null);
};

/** 狼人自爆确认 */
const handleWolfSelfDestruct = async () => {
  try {
    await ElMessageBox.confirm(
      '自爆后将立即死亡并跳过白天剩余流程，确定要自爆吗？',
      '狼人自爆',
      { confirmButtonText: '确定自爆', cancelButtonText: '取消', type: 'warning' },
    );
    send({ type: 'wolf_self_destruct', payload: {} });
  } catch {
    // 用户取消
  }
};

/** 预言家查验结果（网易规则：仅显示阵营，不显示具体角色） */
const prophetCheckDisplay = computed(() => {
  if (!store.prophetCheckResult) return null;
  const isWolf = store.prophetCheckResult.role === 'wolf';
  return {
    seatLabel: store.prophetCheckResult.seatLabel,
    roleLabel: isWolf ? '狼人' : '好人',
    role: store.prophetCheckResult.role,
  };
});

/** 投票结果汇总 */
const voteSummaryDisplay = computed(() => {
  if (!store.voteSummary?.votes.length) return null;
  const grouped: Record<string, { targetSeat: number; targetName: string; voterSeats: number[]; voterNames: string[] }> = {};
  const abstainVoters: { voterSeat: number; voterName: string }[] = [];
  for (const v of store.voteSummary.votes) {
    if (v.targetId === 'abstain') {
      const vSeat = v.voterSeat ?? store.players.find((p) => p.id === v.voterId)?.seatNumber ?? 0;
      const vName = store.players.find((p) => p.id === v.voterId)?.name ?? '';
      abstainVoters.push({ voterSeat: vSeat, voterName: vName });
    } else {
      const tSeat = v.targetSeat ?? store.players.find((p) => p.id === v.targetId)?.seatNumber ?? 0;
      const tName = store.players.find((p) => p.id === v.targetId)?.name ?? '';
      const vSeat = v.voterSeat ?? store.players.find((p) => p.id === v.voterId)?.seatNumber ?? 0;
      const vName = store.players.find((p) => p.id === v.voterId)?.name ?? '';
      if (!grouped[tSeat]) {
        grouped[tSeat] = { targetSeat: tSeat, targetName: tName, voterSeats: [], voterNames: [] };
      }
      grouped[tSeat].voterSeats.push(vSeat);
      grouped[tSeat].voterNames.push(vName);
    }
  }
  const result = Object.values(grouped).sort((a, b) => b.voterSeats.length - a.voterSeats.length);
  return { targets: result, abstainVoters };
});

// 当投票结果变化且不为空时，显示弹窗
watch(voteSummaryDisplay, (newVal) => {
  if (newVal && (newVal.targets.length > 0 || newVal.abstainVoters.length > 0)) {
    showVoteSummaryDialog.value = true;
  }
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
    if (store.isLastWords) {
      send({ type: 'last_words', payload: { content } });
      store.setIsLastWords(false);
    } else {
      await apiSpeak(store.gameId, store.myId, content);
    }
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

const submitNightActionHandler = async (targetId: string, actionType?: string) => {
  try {
    await apiNightAction(store.gameId, store.myId, targetId, actionType);
    store.setNightActionRequired(false);
    ElMessage.success('夜间行动已提交');
  } catch (error) {
    ElMessage.error(getErrorMessage(error, '提交夜间行动失败'));
  }
};

/** 处理点击玩家座位的交互 (替代底部的 ActionPanel 选择) */
const handleSeatClick = (targetId: string) => {
  const targetPlayer = store.players.find(p => p.id === targetId);
  if (!targetPlayer) return;

  // 如果是投票阶段，且自己可以投票
  if (store.gameStatus === 'vote' && canPlayerVote(store.gameStatus, selfPlayer.value ?? undefined)) {
    if (!targetPlayer.isAlive) {
      ElMessage.warning('不能投票给已出局的玩家');
      return;
    }
    if (targetId === store.myId) {
      ElMessage.warning('不能投票给自己');
      return;
    }
    ElMessageBox.confirm(
      `确定要投票给 ${targetPlayer.seatNumber}号(${targetPlayer.name}) 吗？`,
      '确认投票',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    ).then(() => {
      submitVote(targetId);
    }).catch(() => {});
    return;
  }

  // 如果是夜间行动阶段，且自己需要行动
  if (showNightAction.value) {
    if (!targetPlayer.isAlive && store.myRole !== 'witch') {
      // 只有女巫救人的时候才可以点已经"死"(即将死)的人，但正常情况下女巫不通过点击刀口来救人，直接在下面操作，这里加一个基础限制
      ElMessage.warning('目标玩家已出局');
      return;
    }
    // 狼人刀人
    if (store.myRole === 'wolf') {
      if (store.wolfTeammates.includes(targetPlayer.seatNumber)) {
        ElMessage.warning('不能袭击狼人队友');
        return;
      }
      ElMessageBox.confirm(
        `确定要袭击 ${targetPlayer.seatNumber}号(${targetPlayer.name}) 吗？`,
        '夜间袭击',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'error' }
      ).then(() => {
        submitNightActionHandler(targetId);
      }).catch(() => {});
      return;
    }
    // 预言家验人
    if (store.myRole === 'prophet') {
      if (targetId === store.myId) {
        ElMessage.warning('不能查验自己');
        return;
      }
      ElMessageBox.confirm(
        `确定要查验 ${targetPlayer.seatNumber}号(${targetPlayer.name}) 的身份吗？`,
        '预言家查验',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
      ).then(() => {
        submitNightActionHandler(targetId);
      }).catch(() => {});
      return;
    }
    // 女巫、守卫等其他角色的逻辑需要结合具体动作，可能需要弹窗选择技能
    // 对于女巫可能需要区分毒药和解药
    if (store.myRole === 'witch') {
      // 检查解药情况
      if (!selfPlayer.value?.antidoteUsed && targetId === store.wolfKillTargetId) {
         ElMessageBox.confirm(
           `该玩家今晚被袭击了，你要使用解药救活他吗？`,
           '女巫解药',
           { confirmButtonText: '使用解药', cancelButtonText: '取消', type: 'warning' }
         ).then(() => {
           submitNightActionHandler(targetId, 'save');
         }).catch(() => {});
         return;
      }
      
      if (!selfPlayer.value?.poisonUsed) {
        if (targetId === store.myId) {
           ElMessage.warning('不能毒杀自己');
           return;
        }
        ElMessageBox.confirm(
          `确定要对 ${targetPlayer.seatNumber}号(${targetPlayer.name}) 使用毒药吗？`,
          '女巫撒毒',
          { confirmButtonText: '使用毒药', cancelButtonText: '取消', type: 'error' }
        ).then(() => {
          submitNightActionHandler(targetId, 'poison');
        }).catch(() => {});
      } else {
        ElMessage.warning('毒药已使用或不可用');
      }
      return;
    }
    if (store.myRole === 'guard') {
      ElMessageBox.confirm(
        `确定要守护 ${targetPlayer.seatNumber}号(${targetPlayer.name}) 吗？`,
        '守卫守护',
        { confirmButtonText: '守护', cancelButtonText: '取消', type: 'success' }
      ).then(() => {
        submitNightActionHandler(targetId);
      }).catch(() => {});
      return;
    }
  }
};

onMounted(() => {
  if (store.gameId && store.myId) {
    connect(store.gameId, store.myId);
  }
  // 进入对局页时清空翻牌队列，避免上一局残留
  clearReveal();
  // 防止刷新/重连后重复弹历史翻牌：把当前已存在的翻牌状态预填进已见集合
  for (const p of store.players) {
    if (p.isIdiotRevealed) lastSeenReveals.value.add(`idiot:${p.id}`);
    if (p.publicRole === 'hunter') lastSeenReveals.value.add(`hunter:${p.id}`);
  }
  // 防止刷新后重复弹身份卡：若 store 已恢复出真实角色，标记本局已弹过
  if (store.myRole !== 'unknown' && store.gameId) {
    try {
      sessionStorage.setItem(`wolfbot.roleRevealed.${store.gameId}`, '1');
    } catch { /* sessionStorage 不可用则忽略 */ }
  }
});

/** 角色名称（仅 hunter/idiot/wolf 在 watch 中使用，已直接写字面量） */
function playerLabel(playerId: string): string {
  const p = store.players.find((x) => x.id === playerId);
  return p ? `${p.seatNumber}号(${p.name})` : '';
}

/** 触发点 1：自己被分配身份（私密翻牌） */
watch(
  () => store.myRole,
  (role, prev) => {
    if (role !== 'unknown' && (prev === undefined || prev === 'unknown')) {
      // sessionStorage 兜底：同一局只弹一次
      const key = `wolfbot.roleRevealed.${store.gameId}`;
      try {
        if (sessionStorage.getItem(key) === '1') return;
        sessionStorage.setItem(key, '1');
      } catch { /* 忽略 */ }
      reveal({ role, name: playerLabel(store.myId), mode: 'private', title: '你的身份是' });
    }
  },
);

/** 触发点 2：狼人自爆（公开翻牌） */
watch(
  () => store.wolfSelfDestructed,
  (payload, prev) => {
    if (payload && !prev) {
      reveal({
        role: 'wolf',
        name: payload.playerName,
        mode: 'public',
        title: '狼人自爆',
      });
    }
  },
);

/** 触发点 3 & 4：白痴翻牌 / 猎人翻牌（公开翻牌） */
const playerRevealKeys = computed(() =>
  store.players.map((p) => `${p.id}|${p.isIdiotRevealed ? '1' : '0'}|${p.publicRole ?? ''}`).join(','),
);
const lastSeenReveals = ref<Set<string>>(new Set());
watch(playerRevealKeys, () => {
  const seen = lastSeenReveals.value;
  for (const p of store.players) {
    // 白痴翻牌
    if (p.isIdiotRevealed) {
      const key = `idiot:${p.id}`;
      if (!seen.has(key)) {
        seen.add(key);
        reveal({
          role: 'idiot',
          name: `${p.seatNumber}号(${p.name})`,
          mode: 'public',
          title: '翻牌：白痴',
        });
      }
    }
    // 猎人翻牌
    if (p.publicRole === 'hunter') {
      const key = `hunter:${p.id}`;
      if (!seen.has(key)) {
        seen.add(key);
        reveal({
          role: 'hunter',
          name: `${p.seatNumber}号(${p.name})`,
          mode: 'public',
          title: '翻牌：猎人',
        });
      }
    }
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
/* 三段式布局容器 */
.game-play-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  width: 100%;
  background: var(--bg-primary);
  transition: background 1s ease-in-out, color 1s ease-in-out;
  padding: 12px;
  gap: 12px;
  position: relative;
  overflow-x: hidden;
  box-sizing: border-box;
}

/* 沉浸式背景 */
.immersive-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
  opacity: 0.3;
  transition: opacity 2s ease-in-out, background 2s ease-in-out;
  background: linear-gradient(to bottom, #87CEEB 0%, #E0F6FF 100%);
}

.immersive-bg.is-night {
  opacity: 0.8;
  background: linear-gradient(to bottom, #0A0A2A 0%, #1A1A3A 100%);
}

/* 背景底图层（用户上传 bg-day/night.webp 后自动生效） */
.bg-image-layer {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  opacity: 0.55;
  transition: opacity 1.5s ease-in-out;
  pointer-events: none;
}
.bg-image-layer.is-night {
  opacity: 0.75;
}

.moon-or-sun {
  position: absolute;
  top: 20px;
  right: 40px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #FFFDE7, #FFF59D);
  box-shadow: 0 0 20px #FFF59D;
  transition: all 2s ease-in-out;
}

.immersive-bg.is-night .moon-or-sun {
  top: 40px;
  right: 60px;
  width: 50px;
  height: 50px;
  background: radial-gradient(circle at 70% 30%, transparent 40%, #E0E0E0 100%);
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.2);
  transform: rotate(-30deg);
}

.immersive-bg .stars {
  position: absolute;
  width: 100%;
  height: 100%;
  background-image: 
    radial-gradient(1px 1px at 20px 30px, #eee, rgba(0,0,0,0)),
    radial-gradient(1px 1px at 40px 70px, #fff, rgba(0,0,0,0)),
    radial-gradient(1px 1px at 50px 160px, #ddd, rgba(0,0,0,0)),
    radial-gradient(2px 2px at 90px 40px, #fff, rgba(0,0,0,0)),
    radial-gradient(2px 2px at 130px 80px, #fff, rgba(0,0,0,0));
  background-repeat: repeat;
  background-size: 200px 200px;
  opacity: 0;
  transition: opacity 2s ease-in-out;
}

.immersive-bg.is-night .stars {
  opacity: 0.6;
}

/* 顶栏 */
.game-top-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
  padding: 8px 12px;
  background: var(--bg-card);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  transition: background 0.5s ease, border-color 0.5s ease;
  z-index: 1;
}

.top-bar-spacer {
  flex: 1;
}

/* 中央区域：圆桌 */
.game-center {
  flex: 1;
  min-height: 360px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: background 0.5s ease;
  z-index: 1;
}

/* 中央浮动内容 */
.center-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-height: 180px;
  overflow-y: auto;
  padding: 8px;
  z-index: 1;
}

.speaker-hint {
  pointer-events: auto;
}

/* 底部操作栏 */
.game-bottom-bar {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  position: sticky;
  bottom: 0;
  background: var(--bg-card-glass);
  backdrop-filter: blur(8px);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  padding: 8px;
  transition: background 0.5s ease, border-color 0.5s ease;
  z-index: 1;
}

.chat-wrapper {
  flex: 2;
  min-width: 300px;
  max-height: 360px;
  display: flex;
  flex-direction: column;
}

/* 操作面板区域 */
.action-panels {
  flex: 1;
  min-width: 280px;
  max-height: 360px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 投票结果卡片 */
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
  border-bottom: 1px solid var(--border-color);
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
  color: var(--faction-wolf, #ef4444);
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

.abstain-row {
  border-top: 1px dashed var(--border-color);
  padding-top: 8px;
}

.prophet-check-card {
  animation: fadeIn 0.3s ease;
}

/* 发言方向选择卡片 */
.speak-direction-card {
  animation: fadeIn 0.3s ease;
}

.speak-direction-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.speak-direction-actions {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

/* 渐入动画 */
.animate-fade-in {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 768px) {
  .game-bottom-bar {
    flex-direction: column;
  }
  .action-panels {
    min-width: unset;
  }
}
</style>
