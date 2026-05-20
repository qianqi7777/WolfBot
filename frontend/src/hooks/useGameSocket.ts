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
} from '@/types/game';

const GAME_STATUSES: GameStatus[] = ['waiting', 'role_select', 'night', 'day', 'speak', 'vote', 'end'];
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

export function useGameSocket() {
  const socket = ref<WebSocket | null>(null);
  const isConnected = ref(false);
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
          store.updatePlayerStatus(message.payload.playerId, message.payload.isAlive);
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
          const payload = message.payload as SpeakTurnPayload;
          if (isNullableString(payload.currentSpeakerId)) {
            store.setCurrentSpeakerId(payload.currentSpeakerId);
          }
          if (typeof payload.deadline === 'string') {
            store.setDeadline(payload.deadline);
          }
          if (typeof (message.payload as Record<string, unknown>).totalSeconds === 'number') {
            store.setCurrentPhaseTimeout((message.payload as Record<string, unknown>).totalSeconds as number);
          }
          // 遗言标记
          const isLastWords = (message.payload as Record<string, unknown>).isLastWords === true;
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
          store.setWolfTeammates(message.payload.teammates.filter((t: unknown) => typeof t === 'string'));
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
          let checkedPlayerId: string | null = null;
          let checkedRole: RoleType | null = null;
          // Backend sends checkedResults: [{playerId, targetId, isWolf}]
          // Find the result for the current player
          if (Array.isArray(message.payload.checkedResults)) {
            const myResult = message.payload.checkedResults.find(
              (r: unknown) => isRecord(r) && r.playerId === store.myId,
            );
            if (myResult && isRecord(myResult)) {
              checkedPlayerId = typeof myResult.targetId === 'string' ? myResult.targetId : null;
              if (myResult.isWolf === true) {
                checkedRole = 'wolf';
              } else if (isRoleType(myResult.checkedRole)) {
                checkedRole = myResult.checkedRole;
              } else {
                checkedRole = 'civilian';
              }
            }
          }
          const result: NightResultPayload = {
            killedPlayerId: typeof message.payload.killedPlayerId === 'string' ? message.payload.killedPlayerId : null,
            guardedPlayerId: typeof message.payload.guardedPlayerId === 'string' ? message.payload.guardedPlayerId : null,
            guardBlocked: typeof message.payload.guardBlocked === 'boolean' ? message.payload.guardBlocked : undefined,
            checkedResults: Array.isArray(message.payload.checkedResults)
              ? message.payload.checkedResults.filter(
                  (r: unknown) =>
                    isRecord(r) &&
                    typeof r.playerId === 'string' &&
                    typeof r.targetId === 'string' &&
                    typeof r.isWolf === 'boolean',
                )
              : undefined,
            checkedPlayerId,
            checkedRole,
          };
          store.setNightResult(result);
          if (result.killedPlayerId) {
            store.updatePlayerStatus(result.killedPlayerId, false);
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
