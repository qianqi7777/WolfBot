import axios from 'axios';

import type { AiConfigForm, AiConnectionTestResult, GameResultPayload, GameSnapshot, RoomSettingsForm } from '@/types/game';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  timeout: 10000,
});

export async function createGame(playerName = '玩家'): Promise<GameSnapshot> {
  const { data } = await api.post<GameSnapshot>('/api/games', { playerName });
  return data;
}

export async function joinGame(gameId: string, playerName = '玩家', preferredSeat?: number): Promise<GameSnapshot> {
  const payload: Record<string, unknown> = { playerName };
  if (preferredSeat !== undefined) payload.preferredSeat = preferredSeat;
  const { data } = await api.post<GameSnapshot>(`/api/rooms/${gameId}/join`, payload);
  return data;
}

export async function getGame(gameId: string, playerId?: string): Promise<GameSnapshot> {
  const params = playerId ? { params: { playerId } } : undefined;
  const { data } = await api.get<GameSnapshot>(`/api/games/${gameId}`, params);
  return data;
}

export async function getRoom(gameId: string, playerId?: string): Promise<GameSnapshot> {
  const params = playerId ? { params: { playerId } } : undefined;
  const { data } = await api.get<GameSnapshot>(`/api/rooms/${gameId}`, params);
  return data;
}

export async function changeSeat(gameId: string, playerId: string, seatNumber: number): Promise<GameSnapshot> {
  const { data } = await api.put<GameSnapshot>(`/api/rooms/${gameId}/seat`, { playerId, seatNumber });
  return data;
}

export async function startGame(gameId: string, playerId?: string): Promise<GameSnapshot> {
  const params = playerId ? { params: { playerId } } : undefined;
  const { data } = await api.post<GameSnapshot>(`/api/rooms/${gameId}/start`, null, params);
  return data;
}

export async function updateRoomSettings(gameId: string, settings: RoomSettingsForm): Promise<GameSnapshot> {
  const { data } = await api.patch<GameSnapshot>(`/api/rooms/${gameId}/settings`, settings);
  return data;
}

export async function testRoomAiConnection(gameId: string, aiConfig?: AiConfigForm): Promise<AiConnectionTestResult> {
  const { data } = await api.post<AiConnectionTestResult>(`/api/rooms/${gameId}/ai/test`, aiConfig ?? {});
  return data;
}

export async function submitSpeak(gameId: string, playerId: string, content: string): Promise<void> {
  await api.post(`/api/games/${gameId}/action/speak`, { content, playerId });
}

export async function submitVote(gameId: string, playerId: string, targetId: string): Promise<void> {
  await api.post(`/api/games/${gameId}/action/vote`, { targetId, playerId });
}

export async function submitNightAction(gameId: string, playerId: string, targetId: string): Promise<void> {
  await api.post(`/api/games/${gameId}/action/night`, { playerId, targetId });
}

export async function getResult(gameId: string): Promise<GameResultPayload> {
  const { data } = await api.get<GameResultPayload>(`/api/games/${gameId}/result`);
  return data;
}
