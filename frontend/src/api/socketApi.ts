export function buildGameSocketUrl(gameId: string, playerId: string): string {
  const baseUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/game';
  const url = new URL(baseUrl);
  url.searchParams.set('gameId', gameId);
  url.searchParams.set('playerId', playerId);
  return url.toString();
}
