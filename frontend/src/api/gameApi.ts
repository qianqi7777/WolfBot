import axios from 'axios';

import type { GameSnapshot, Player } from '@/types/game';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
});

export async function createGame(playerName = '玩家'): Promise<GameSnapshot> {
  const { data } = await api.post<GameSnapshot>('/api/games', { playerName });
  return data;
}

export async function joinGame(gameId: string, playerName = '玩家'): Promise<GameSnapshot> {
  const { data } = await api.post<GameSnapshot>(`/api/games/${gameId}/join`, { playerName });
  return data;
}

export async function getGame(gameId: string): Promise<GameSnapshot> {
  const { data } = await api.get<GameSnapshot>(`/api/games/${gameId}`);
  return data;
}

export async function submitSpeak(gameId: string, content: string): Promise<void> {
  await api.post(`/api/games/${gameId}/action/speak`, { content });
}

export async function submitVote(gameId: string, targetId: string): Promise<void> {
  await api.post(`/api/games/${gameId}/action/vote`, { targetId });
}

export async function getResult(gameId: string): Promise<{ winnerFaction: string; players: Player[] }> {
  const { data } = await api.get<{ winnerFaction: string; players: Player[] }>(`/api/games/${gameId}/result`);
  return data;
}
