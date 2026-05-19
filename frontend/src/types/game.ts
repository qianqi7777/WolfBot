export type GameStatus = 'waiting' | 'night' | 'day' | 'speak' | 'vote' | 'end';

export type RoleType = 'wolf' | 'civilian' | 'prophet' | 'unknown';

export interface Player {
  id: string;
  name: string;
  role: RoleType;
  isAI: boolean;
  isAlive: boolean;
}

export interface ChatMessage {
  id: string;
  playerId: string;
  playerName: string;
  content: string;
  time: string;
  isAI: boolean;
}

export interface VoteData {
  voterId: string;
  targetId: string;
}

export interface AnnounceMessage {
  id: string;
  content: string;
  time: string;
}

export interface SocketMessage<TPayload = Record<string, unknown>> {
  type: 'announce' | 'ai_speak' | 'vote_result' | 'game_status' | 'role_info' | 'player_update' | 'game_over';
  payload?: TPayload;
  timestamp?: string;
}

export interface GameSnapshot {
  gameId: string;
  playerId: string;
  gameStatus: GameStatus;
  players: Player[];
  myRole: RoleType;
}
