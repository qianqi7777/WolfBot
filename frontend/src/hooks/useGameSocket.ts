import { onBeforeUnmount, ref } from 'vue';

import { buildGameSocketUrl } from '@/api/socketApi';
import { useGameStore } from '@/store/modules/gameStore';
import type { SocketMessage } from '@/types/game';

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

    socket.value.onmessage = (event) => {
      const message = JSON.parse(event.data) as SocketMessage;
      handleSocketMessage(message);
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

  const handleSocketMessage = (message: SocketMessage) => {
    switch (message.type) {
      case 'announce':
        store.addAnnounce(String(message.payload?.content ?? ''));
        break;
      case 'game_status':
        if (typeof message.payload?.status === 'string') {
          store.setGameStatus(message.payload.status as never);
        }
        break;
      case 'role_info':
        if (typeof message.payload?.role === 'string') {
          store.setMyRole(message.payload.role as never);
        }
        break;
      case 'player_update':
        if (typeof message.payload?.playerId === 'string' && typeof message.payload?.isAlive === 'boolean') {
          store.updatePlayerStatus(message.payload.playerId, message.payload.isAlive);
        }
        break;
      case 'ai_speak':
      case 'vote_result':
      case 'game_over':
        store.addAnnounce(message.payload?.content ? String(message.payload.content) : message.type);
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
