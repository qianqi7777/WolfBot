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

export interface GameResultPayload {
  gameId: string;
  winnerFaction: string;
  currentRound: number;
  players: Player[];
  chats: ChatMessage[];
  announcements: string[];
}

export interface GameSnapshot {
  gameId: string;
  playerId: string;
  gameStatus: GameStatus;
  currentRound: number;
  started: boolean;
  winnerFaction: string | null;
  players: Player[];
  myRole: RoleType;
}

export interface SocketMessage<TPayload = Record<string, unknown>> {
  type:
    | 'room_update'
    | 'announce'
    | 'ai_speak'
    | 'player_speak'
    | 'vote_result'
    | 'game_status'
    | 'role_info'
    | 'player_update'
    | 'game_over'
    | 'error';
  payload?: TPayload;
  timestamp?: string;
}
