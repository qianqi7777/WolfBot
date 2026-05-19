export type GameStatus = 'waiting' | 'night' | 'day' | 'speak' | 'vote' | 'end';

export type RoleType = 'wolf' | 'civilian' | 'prophet' | 'guard' | 'unknown';

export type ScenePreset = 'six-player-dark';

export interface SceneConfig {
  preset: ScenePreset;
  name: string;
  description: string;
  playerCount: number;
}

export interface AiConfigForm {
  baseUrl: string;
  apiKey: string;
  model: string;
  timeoutSeconds: number;
  temperature: number;
  enableMock: boolean;
}

export interface AiConfigView extends Omit<AiConfigForm, 'apiKey'> {
  hasApiKey: boolean;
}

export interface AiConnectionTestResult {
  success: boolean;
  message: string;
  baseUrl: string;
  model: string;
  enableMock: boolean;
}

export interface RoomSettings {
  scene: SceneConfig;
  ai: AiConfigView;
}

export interface RoomSettingsForm {
  scene: SceneConfig;
  ai: AiConfigForm;
}

export interface Player {
  id: string;
  name: string;
  role: RoleType;
  isAI: boolean;
  isAlive: boolean;
  lastGuardTargetId?: string | null;
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

export interface SpeakTurnPayload {
  currentSpeakerId: string | null;
  currentSpeakerName?: string;
  turnIndex?: number;
  turnCount?: number;
}

// 夜间行动请求载荷
export interface NightActionPayload {
  targetId: string;
  actionType: 'kill' | 'check';
}

// 夜间结果载荷
export interface NightResultPayload {
  killedPlayerId: string | null;
  guardedPlayerId?: string | null;
  guardBlocked?: boolean;
  checkedResults?: Array<{ playerId: string; targetId: string; isWolf: boolean }>;
  checkedPlayerId: string | null;
  checkedRole: RoleType | null;
}

export interface GameSnapshot {
  gameId: string;
  playerId: string;
  gameStatus: GameStatus;
  currentRound: number;
  currentSpeakerId: string | null;
  started: boolean;
  winnerFaction: string | null;
  players: Player[];
  myRole: RoleType;
  nightActionRequired: boolean;
  roomSettings: RoomSettings;
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
    | 'night_action'
    | 'night_result'
    | 'speak_turn'
    | 'error';
  payload?: TPayload;
  timestamp?: string;
}
