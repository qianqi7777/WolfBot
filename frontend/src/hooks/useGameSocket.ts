import { onBeforeUnmount, ref } from 'vue';

import { buildGameSocketUrl } from '@/api/socketApi';
import { useGameStore } from '@/store/modules/gameStore';
import type { ChatMessage, GameResultPayload, GameStatus, Player, RoleType, SocketMessage, VoteData } from '@/types/game';

const GAME_STATUSES: GameStatus[] = ['waiting', 'night', 'day', 'speak', 'vote', 'end'];
const ROLE_TYPES: RoleType[] = ['wolf', 'civilian', 'prophet', 'unknown'];

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

function isPlayer(value: unknown): value is Player {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    typeof value.name === 'string' &&
    isRoleType(value.role) &&
    isBoolean(value.isAI) &&
    isBoolean(value.isAlive)
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

  const connect = (gameId: string, playerId: string) => {
    socket.value?.close();
    socket.value = new WebSocket(buildGameSocketUrl(gameId, playerId));

    socket.value.onopen = () => {
      isConnected.value = true;
    };

    socket.value.onclose = () => {
      isConnected.value = false;
    };

    socket.value.onerror = () => {
      isConnected.value = false;
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

  const disconnect = () => {
    socket.value?.close();
    socket.value = null;
    isConnected.value = false;
  };

  const send = (payload: unknown) => {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(payload));
    }
  };

  const handleRoomUpdate = (message: SocketMessage<{ gameId?: string; players?: unknown[] }>) => {
    if (!Array.isArray(message.payload?.players)) {
      return;
    }

    const players = message.payload.players.filter(isPlayer);
    if (players.length > 0) {
      store.players = players;
    }
  };

  const handleSocketMessage = (message: SocketMessage) => {
    switch (message.type) {
      case 'room_update':
        handleRoomUpdate(message as SocketMessage<{ gameId?: string; players?: unknown[] }>);
        break;
      case 'announce':
        store.addAnnounce(String(message.payload?.content ?? ''));
        break;
      case 'game_status':
        if (isGameStatus(message.payload?.status)) {
          store.setGameStatus(message.payload.status);
        }
        if (typeof message.payload?.currentRound === 'number') {
          store.setCurrentRound(message.payload.currentRound);
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
      case 'vote_result':
        if (isVoteData(message.payload)) {
          store.addVote(message.payload);
        }
        if (typeof message.payload?.content === 'string') {
          store.addAnnounce(message.payload.content);
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
