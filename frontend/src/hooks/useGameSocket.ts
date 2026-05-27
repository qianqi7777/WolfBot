import { onBeforeUnmount, ref } from 'vue';

import { buildGameSocketUrl } from '@/api/socketApi';
import { useGameStore } from '@/store/modules/gameStore';
import type {
  ChatMessage,
  GameResultPayload,
  GameStatus,
  NightResultPayload,
  SpeakTurnPayload,
  Player,
  RoomSettings,
  RoleType,
  SocketMessage,
  VoteData,
  VoteSummaryPayload,
  WolfTargetUpdate,
  RoleSelectStartPayload,
  SheriffElectStartPayload,
  SheriffCampaignPayload,
  SheriffSpeechTurnPayload,
  SheriffVotePayload,
  SheriffElectResultPayload,
  SheriffTransferPayload,
  WolfSelfDestructPayload,
  SpeakDirectionRequestPayload,
} from '@/types/game';

const GAME_STATUSES: GameStatus[] = ['waiting', 'role_select', 'night', 'day', 'sheriff_election', 'speak', 'vote', 'end'];
const ROLE_TYPES: RoleType[] = ['wolf', 'civilian', 'prophet', 'guard', 'hunter', 'witch', 'idiot', 'unknown'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isGameStatus(value: unknown): value is GameStatus {
  return typeof value === 'string' && GAME_STATUSES.includes(value as GameStatus);
}

function isRoleType(value: unknown): value is RoleType {
  return typeof value === 'string' && ROLE_TYPES.includes(value as RoleType);
}

function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean';
}

function isNullableString(value: unknown): value is string | null {
  return typeof value === 'string' || value === null;
}

function isPlayer(value: unknown): value is Player {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    typeof value.seatNumber === 'number' &&
    isRoleType(value.role) &&
    isBoolean(value.isAI) &&
    isBoolean(value.isAlive)
  );
}

function isRoomSettings(value: unknown): value is RoomSettings {
  return (
    isRecord(value) &&
    isRecord(value.scene) &&
    typeof value.scene.preset === 'string' &&
    typeof value.scene.name === 'string' &&
    typeof value.scene.description === 'string' &&
    typeof value.scene.playerCount === 'number' &&
    (value.scene.speakTimeoutSeconds === undefined || typeof value.scene.speakTimeoutSeconds === 'number') &&
    (value.scene.mode === undefined || typeof value.scene.mode === 'string') &&
    isRecord(value.ai) &&
    typeof value.ai.baseUrl === 'string' &&
    typeof value.ai.model === 'string' &&
    typeof value.ai.timeoutSeconds === 'number' &&
    typeof value.ai.temperature === 'number' &&
    isBoolean(value.ai.enableMock) &&
    isBoolean(value.ai.hasApiKey)
  );
}

function isChatMessage(value: unknown): value is ChatMessage {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.playerId === 'string' &&
    typeof value.playerName === 'string' &&
    typeof value.content === 'string' &&
    typeof value.time === 'string' &&
    isBoolean(value.isAI)
  );
}

function isVoteData(value: unknown): value is VoteData {
  return isRecord(value) && typeof value.voterId === 'string' && typeof value.targetId === 'string';
}

function isGameResultPayload(value: unknown): value is GameResultPayload {
  return (
    isRecord(value) &&
    typeof value.gameId === 'string' &&
    typeof value.winnerFaction === 'string' &&
    typeof value.currentRound === 'number' &&
    Array.isArray(value.players) &&
    value.players.every(isPlayer) &&
    Array.isArray(value.chats) &&
    value.chats.every(isChatMessage) &&
    Array.isArray(value.announcements) &&
    value.announcements.every((item) => typeof item === 'string')
  );
}

// 模块级共享 socket，确保所有组件（RoleSelect、SheriffElection 等）使用同一连接
const socket = ref<WebSocket | null>(null);
const isConnected = ref(false);

export function useGameSocket() {
  const store = useGameStore();

  // ── 自动重连机制 ──
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let reconnectAttempts = 0;
  const MAX_RECONNECT_ATTEMPTS = 8;
  const BASE_RECONNECT_DELAY = 1000; // 1s 起步，指数退避

  const clearReconnectTimer = () => {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const scheduleReconnect = (gameId: string, playerId: string) => {
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      store.addAnnounce('连接断开，请刷新页面重试');
      return;
    }
    const delay = BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts);
    reconnectAttempts++;
    store.addAnnounce(`连接断开，${Math.round(delay / 1000)}秒后重连（第${reconnectAttempts}次）`);
    reconnectTimer = setTimeout(() => {
      doConnect(gameId, playerId);
    }, delay);
  };

  const doConnect = (gameId: string, playerId: string) => {
    socket.value?.close();
    socket.value = new WebSocket(buildGameSocketUrl(gameId, playerId));

    socket.value.onopen = () => {
      isConnected.value = true;
      reconnectAttempts = 0; // 重置重连计数
    };

    socket.value.onclose = () => {
      isConnected.value = false;
      scheduleReconnect(gameId, playerId);
    };

    socket.value.onerror = () => {
      isConnected.value = false;
      // onclose 会紧接着触发，由 onclose 处理重连
    };

    socket.value.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as SocketMessage;
        handleSocketMessage(message);
      } catch {
        store.addAnnounce('收到无法解析的消息');
      }
    };
  };

  const connect = (gameId: string, playerId: string) => {
    clearReconnectTimer();
    reconnectAttempts = 0;
    doConnect(gameId, playerId);
  };

  const disconnect = () => {
    clearReconnectTimer();
    reconnectAttempts = MAX_RECONNECT_ATTEMPTS; // 阻止重连
    socket.value?.close();
    socket.value = null;
    isConnected.value = false;
  };

  const send = (payload: unknown) => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(payload));
    }
  };

  const handleRoomUpdate = (
    message: SocketMessage<{ gameId?: string; players?: unknown[]; roomSettings?: unknown; currentSpeakerId?: unknown }>,
  ) => {
    if (!Array.isArray(message.payload?.players)) {
      return;
    }

    const players = message.payload.players.filter(isPlayer);
    if (players.length > 0) {
      store.players = players;
    }
    if (isRecord(message.payload) && isRoomSettings(message.payload.roomSettings)) {
      store.setRoomSettings(message.payload.roomSettings);
    }
    if (isNullableString(message.payload?.currentSpeakerId)) {
      store.setCurrentSpeakerId(message.payload.currentSpeakerId);
    }
  };

  const handleSocketMessage = (message: SocketMessage) => {
    switch (message.type) {
      case 'room_update':
        handleRoomUpdate(
          message as SocketMessage<{
            gameId?: string;
            players?: unknown[];
            roomSettings?: unknown;
            currentSpeakerId?: unknown;
          }>,
        );
        break;
      case 'announce':
        store.addAnnounce(String(message.payload?.content ?? ''));
        break;
      case 'game_status':
        if (isGameStatus(message.payload?.status)) {
          store.setGameStatus(message.payload.status);
          if (message.payload.status !== 'night') {
            store.setNightActionRequired(false);
          }
          if (message.payload.status !== 'speak') {
            store.setCurrentSpeakerId(null);
          }
          // 抢身份阶段清除
          if (message.payload.status !== 'role_select') {
            // 不在抢身份阶段时不清除 roleSelectStart，让结果可显示
          }
          // 非计时阶段清除倒计时
          if (message.payload.status === 'day' || message.payload.status === 'end' || message.payload.status === 'waiting') {
            store.setDeadline(null);
          }
        }
        if (typeof message.payload?.currentRound === 'number') {
          store.setCurrentRound(message.payload.currentRound);
        }
        if (isNullableString(message.payload?.currentSpeakerId)) {
          store.setCurrentSpeakerId(message.payload.currentSpeakerId);
        }
        // 提取 deadline
        if (typeof message.payload?.deadline === 'string') {
          store.setDeadline(message.payload.deadline);
        }
        // 提取 totalSeconds（倒计时进度条总量）
        if (typeof message.payload?.totalSeconds === 'number') {
          store.setCurrentPhaseTimeout(message.payload.totalSeconds);
        }
        // 提取 gameMode
        if (typeof message.payload?.gameMode === 'string') {
          store.setGameMode(message.payload.gameMode as 'classic' | 'role_select');
        }
        break;
      case 'role_info':
        if (isRoleType(message.payload?.role)) {
          store.setMyRole(message.payload.role);
        }
        break;
      case 'player_update':
        if (typeof message.payload?.playerId === 'string' && isBoolean(message.payload?.isAlive)) {
          const isSheriff = isBoolean(message.payload?.isSheriff) ? message.payload.isSheriff as boolean : undefined;
          const revealedRole = isRoleType(message.payload?.revealedRole)
            ? message.payload.revealedRole as RoleType
            : undefined;
          const publicRole = isRoleType(message.payload?.publicRole)
            ? message.payload.publicRole as RoleType
            : undefined;
          const isIdiotRevealed = isBoolean(message.payload?.isIdiotRevealed)
            ? message.payload.isIdiotRevealed as boolean
            : undefined;
          store.updatePlayerStatus(
            message.payload.playerId,
            message.payload.isAlive,
            isSheriff,
            revealedRole,
            isIdiotRevealed,
            publicRole,
          );
          // revealedRole 仅出现在预言家私发的查验结果中：仅预言家本人收到
          if (
            revealedRole
            && store.myRole === 'prophet'
            && typeof message.payload?.playerName === 'string'
          ) {
            store.setProphetCheckResult({
              seatLabel: message.payload.playerName,
              role: revealedRole,
            });
          }
        }
        break;
      case 'player_speak':
      case 'ai_speak':
        if (typeof message.payload?.content === 'string') {
          store.addChatMessage({
            id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
            playerId: typeof message.payload?.playerId === 'string' ? message.payload.playerId : '',
            playerName: typeof message.payload?.playerName === 'string' ? message.payload.playerName : '玩家',
            content: message.payload.content,
            time: message.timestamp ?? new Date().toISOString(),
            isAI: message.type === 'ai_speak' || Boolean(message.payload?.isAI),
          });
        }
        break;
      case 'speak_turn':
        if (isRecord(message.payload)) {
          const payload = message.payload as Record<string, unknown>;
          if (isNullableString(payload.currentSpeakerId)) {
            store.setCurrentSpeakerId(payload.currentSpeakerId);
          }
          if (typeof payload.deadline === 'string') {
            store.setDeadline(payload.deadline);
          }
          if (typeof payload.totalSeconds === 'number') {
            store.setCurrentPhaseTimeout(payload.totalSeconds as number);
          }
          // 遗言标记
          const isLastWords = payload.isLastWords === true;
          store.setIsLastWords(isLastWords);
        }
        break;
      case 'vote_result':
        if (isVoteData(message.payload)) {
          store.addVote(message.payload);
        }
        if (typeof message.payload?.content === 'string') {
          store.addAnnounce(message.payload.content);
        }
        break;
      case 'vote_summary':
        if (isRecord(message.payload) && Array.isArray(message.payload.votes)) {
          const votes = message.payload.votes.filter(
            (v: unknown) => isRecord(v) && typeof v.voterId === 'string' && typeof v.targetId === 'string',
          ) as VoteData[];
          store.setVoteSummary({
            votes,
            eliminated: typeof message.payload.eliminated === 'string' ? message.payload.eliminated : null,
          });
        }
        break;
      case 'night_action':
        if (isRecord(message.payload) && 'actionRequired' in message.payload) {
          store.setNightActionRequired(!!message.payload.actionRequired);
        }
        // 狼人队友信息
        if (isRecord(message.payload) && Array.isArray(message.payload.teammates)) {
          // payload.teammates is ['1号', '3号'] -> parse out numbers
          const teammateSeats = message.payload.teammates
            .filter((t: unknown) => typeof t === 'string')
            .map((t: string) => parseInt(t.replace('号', ''), 10))
            .filter((n: number) => !isNaN(n));
          store.setWolfTeammates(teammateSeats);
        }
        // 女巫刀口信息：
        // - 新夜开始时先重置为待定，提示等待狼人选择目标
        // - 有刀口时写入具体目标
        // - 夜晚结算后没有死亡时再落成 none
        if (isRecord(message.payload) && message.payload.role === 'witch' && message.payload.actionRequired === true) {
          const hasWolfTargetId = 'wolfKillTargetId' in message.payload;
          const hasWolfTargetLabel = 'wolfKillTargetLabel' in message.payload;
          if (hasWolfTargetId || hasWolfTargetLabel) {
            const wolfTargetId = typeof message.payload.wolfKillTargetId === 'string' ? message.payload.wolfKillTargetId : null;
            const wolfTargetLabel = typeof message.payload.wolfKillTargetLabel === 'string' ? message.payload.wolfKillTargetLabel : null;
            store.setWolfKillTarget(wolfTargetId, wolfTargetLabel);
          } else {
            store.setWolfKillTarget(null, null);
          }
        }
        // 提取 deadline
        if (isRecord(message.payload) && typeof message.payload.deadline === 'string') {
          store.setDeadline(message.payload.deadline);
        }
        // 提取 totalSeconds
        if (isRecord(message.payload) && typeof message.payload.totalSeconds === 'number') {
          store.setCurrentPhaseTimeout(message.payload.totalSeconds);
        }
        break;
      case 'night_result':
        if (isRecord(message.payload)) {
          // checkedResults 不再从广播获取——预言家查验结果仅通过私发 announce 传递
          const result: NightResultPayload = {
            killedPlayerId: typeof message.payload.killedPlayerId === 'string' ? message.payload.killedPlayerId : null,
            guardedPlayerId: typeof message.payload.guardedPlayerId === 'string' ? message.payload.guardedPlayerId : null,
            guardBlocked: typeof message.payload.guardBlocked === 'boolean' ? message.payload.guardBlocked : undefined,
            witchSaved: typeof message.payload.witchSaved === 'boolean' ? message.payload.witchSaved : undefined,
            witchSavedPlayerId: typeof message.payload.witchSavedPlayerId === 'string' ? message.payload.witchSavedPlayerId : null,
            witchPoisonedPlayerId: typeof message.payload.witchPoisonedPlayerId === 'string' ? message.payload.witchPoisonedPlayerId : null,
            allKilledIds: Array.isArray(message.payload.allKilledIds)
              ? message.payload.allKilledIds.filter((id: unknown) => typeof id === 'string')
              : undefined,
          };
          store.setNightResult(result);
          const killedIds = result.allKilledIds?.length
            ? result.allKilledIds
            : (result.killedPlayerId ? [result.killedPlayerId] : []);
          for (const deadId of killedIds) {
            store.updatePlayerStatus(deadId, false);
          }
          if (!killedIds.length) {
            store.setWolfKillTarget('none', null);
          }
        }
        break;
      case 'wolf_target_update':
        if (isRecord(message.payload) &&
            typeof message.payload.wolfId === 'string' &&
            typeof message.payload.wolfSeat === 'number' &&
            typeof message.payload.targetId === 'string' &&
            typeof message.payload.targetSeat === 'number' &&
            typeof message.payload.message === 'string') {
          store.addWolfTargetUpdate({
            wolfId: message.payload.wolfId,
            wolfSeat: message.payload.wolfSeat,
            targetId: message.payload.targetId,
            targetSeat: message.payload.targetSeat,
            message: message.payload.message,
          } as WolfTargetUpdate);
        }
        break;
      case 'role_select_start':
        if (isRecord(message.payload) && Array.isArray(message.payload.availableRoles)) {
          store.setRoleSelectStart({
            availableRoles: message.payload.availableRoles.filter((r: unknown) => typeof r === 'string'),
            timeoutSeconds: typeof message.payload.timeoutSeconds === 'number' ? message.payload.timeoutSeconds : 10,
            message: typeof message.payload.message === 'string' ? message.payload.message : '',
            deadline: typeof message.payload.deadline === 'string' ? message.payload.deadline : '',
            totalSeconds: typeof message.payload.totalSeconds === 'number' ? message.payload.totalSeconds : 10,
          });
          store.setMySelectedRole(null);
        }
        break;
      case 'role_select_result':
        if (isRecord(message.payload) && typeof message.payload.message === 'string') {
          store.addAnnounce(message.payload.message);
          // 抢身份阶段结束，清除抢身份状态
          store.setRoleSelectStart(null);
        }
        break;
      case 'game_over':
        if (isGameResultPayload(message.payload)) {
          store.setResult(message.payload);
        } else if (typeof message.payload?.content === 'string') {
          store.addAnnounce(message.payload.content);
        }
        break;
      case 'sheriff_elect_start':
        if (isRecord(message.payload)) {
          const electPayload: SheriffElectStartPayload = {
            phase: typeof message.payload.phase === 'string' ? message.payload.phase as 'campaign' | 'speech' | 'vote' : 'campaign',
            deadline: typeof message.payload.deadline === 'string' ? message.payload.deadline : '',
            totalSeconds: typeof message.payload.totalSeconds === 'number' ? message.payload.totalSeconds : 5,
            candidateIds: Array.isArray(message.payload.candidateIds)
              ? message.payload.candidateIds.filter((id: unknown) => typeof id === 'string')
              : [],
          };
          store.setSheriffElectStart(electPayload);
          if (typeof message.payload.deadline === 'string') {
            store.setDeadline(message.payload.deadline);
          }
          if (typeof message.payload.totalSeconds === 'number') {
            store.setCurrentPhaseTimeout(message.payload.totalSeconds);
          }
        }
        break;
      case 'sheriff_campaign':
        if (isRecord(message.payload)) {
          const campaignPayload: SheriffCampaignPayload = {
            action: typeof message.payload.action === 'string' ? message.payload.action as 'run' | 'withdraw' | 'register_done' : 'register_done',
            playerId: typeof message.payload.playerId === 'string' ? message.payload.playerId : undefined,
            playerName: typeof message.payload.playerName === 'string' ? message.payload.playerName : undefined,
            candidateIds: Array.isArray(message.payload.candidateIds)
              ? message.payload.candidateIds.filter((id: unknown) => typeof id === 'string')
              : [],
            withdrewIds: Array.isArray(message.payload.withdrewIds)
              ? (message.payload.withdrewIds as unknown[]).filter((id) => typeof id === 'string') as string[]
              : undefined,
          };
          store.setSheriffCandidateIds(campaignPayload.candidateIds);
          if (campaignPayload.withdrewIds) {
            store.setSheriffWithdrewIds(campaignPayload.withdrewIds);
          }
          // 也更新 store 的选举开始 payload 中的候选列表
          if (store.sheriffElectStart) {
            store.sheriffElectStart.candidateIds = campaignPayload.candidateIds;
          }
          // 公告
          if (campaignPayload.action === 'run' && campaignPayload.playerName) {
            store.addAnnounce(`${campaignPayload.playerName} 上警竞选`);
          } else if (campaignPayload.action === 'withdraw' && campaignPayload.playerName) {
            store.addAnnounce(`${campaignPayload.playerName} 退选`);
          }
        }
        break;
      case 'sheriff_speech_turn':
        if (isRecord(message.payload)) {
          const speechPayload: SheriffSpeechTurnPayload = {
            currentSpeakerId: typeof message.payload.currentSpeakerId === 'string' ? message.payload.currentSpeakerId : '',
            currentSpeakerName: typeof message.payload.currentSpeakerName === 'string' ? message.payload.currentSpeakerName : '',
            turnIndex: typeof message.payload.turnIndex === 'number' ? message.payload.turnIndex : 1,
            turnCount: typeof message.payload.turnCount === 'number' ? message.payload.turnCount : 1,
            deadline: typeof message.payload.deadline === 'string' ? message.payload.deadline : '',
            totalSeconds: typeof message.payload.totalSeconds === 'number' ? message.payload.totalSeconds : 15,
            canWithdraw: message.payload.canWithdraw === true,
            isPk: message.payload.isPk === true,
          };
          store.setSheriffSpeechTurn(speechPayload);
          store.setCurrentSpeakerId(speechPayload.currentSpeakerId);
          if (speechPayload.deadline) {
            store.setDeadline(speechPayload.deadline);
          }
          store.setCurrentPhaseTimeout(speechPayload.totalSeconds);
        }
        break;
      case 'sheriff_vote':
        if (isRecord(message.payload) && Array.isArray(message.payload.candidateIds)) {
          const votePayload: SheriffVotePayload = {
            candidateIds: message.payload.candidateIds.filter((id: unknown) => typeof id === 'string'),
            deadline: typeof message.payload.deadline === 'string' ? message.payload.deadline : '',
            totalSeconds: typeof message.payload.totalSeconds === 'number' ? message.payload.totalSeconds : 30,
          };
          store.setSheriffVoteStart(votePayload);
          if (votePayload.deadline) {
            store.setDeadline(votePayload.deadline);
          }
          store.setCurrentPhaseTimeout(votePayload.totalSeconds);
        }
        break;
      case 'sheriff_elect_result':
        if (isRecord(message.payload)) {
          const resultPayload: SheriffElectResultPayload = {
            sheriffId: typeof message.payload.sheriffId === 'string' ? message.payload.sheriffId : null,
            isTie: typeof message.payload.isTie === 'boolean' ? message.payload.isTie : false,
            message: typeof message.payload.message === 'string' ? message.payload.message : '',
          };
          store.setSheriffElectResult(resultPayload);
          store.setSheriffId(resultPayload.sheriffId);
          if (resultPayload.message) {
            store.addAnnounce(resultPayload.message);
          }
        }
        break;
      case 'wolf_self_destruct':
        if (isRecord(message.payload)) {
          const destructPayload: WolfSelfDestructPayload = {
            playerId: typeof message.payload.playerId === 'string' ? message.payload.playerId : '',
            playerName: typeof message.payload.playerName === 'string' ? message.payload.playerName : '',
            playerRole: 'wolf',
          };
          store.setWolfSelfDestructed(destructPayload);
          store.updatePlayerStatus(destructPayload.playerId, false);
          store.addAnnounce(`⚠️ ${destructPayload.playerName} 自爆了！身份是狼人！`);
        }
        break;
      case 'speak_direction_request':
        if (isRecord(message.payload) && typeof message.payload.sheriffId === 'string') {
          const directionPayload: SpeakDirectionRequestPayload = {
            sheriffId: message.payload.sheriffId,
            deadline: typeof message.payload.deadline === 'string' ? message.payload.deadline : undefined,
            totalSeconds: typeof message.payload.totalSeconds === 'number' ? message.payload.totalSeconds : undefined,
          };
          store.setSpeakDirectionRequest(directionPayload);
          if (directionPayload.deadline) {
            store.setDeadline(directionPayload.deadline);
          }
          if (directionPayload.totalSeconds) {
            store.setCurrentPhaseTimeout(directionPayload.totalSeconds);
          }
          store.addAnnounce('警长正在选择发言方向...');
        }
        break;
      case 'sheriff_transfer':
        if (isRecord(message.payload)) {
          const transferPayload: SheriffTransferPayload = {
            fromPlayerId: typeof message.payload.fromPlayerId === 'string' ? message.payload.fromPlayerId : '',
            toPlayerId: typeof message.payload.toPlayerId === 'string' ? message.payload.toPlayerId : undefined,
            toPlayerName: typeof message.payload.toPlayerName === 'string' ? message.payload.toPlayerName : undefined,
            needsChoice: typeof message.payload.needsChoice === 'boolean' ? message.payload.needsChoice : undefined,
            candidateIds: Array.isArray(message.payload.candidateIds)
              ? message.payload.candidateIds.filter((id: unknown) => typeof id === 'string')
              : undefined,
          };
          store.setSheriffTransfer(transferPayload);
          if (transferPayload.toPlayerId) {
            store.setSheriffId(transferPayload.toPlayerId);
          }
          if (transferPayload.needsChoice) {
            // 警长死亡需要选择继承人
            store.addAnnounce('警长死亡，请选择继承人转让徽章');
          }
        }
        break;
      case 'error':
        if (typeof message.payload?.content === 'string') {
          store.addAnnounce(`错误：${message.payload.content}`);
        }
        break;
      default:
        break;
    }
  };

  onBeforeUnmount(disconnect);

  return {
    socket,
    isConnected,
    connect,
    disconnect,
    send,
  };
}
