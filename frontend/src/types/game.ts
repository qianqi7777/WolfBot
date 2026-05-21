export type GameStatus = 'waiting' | 'role_select' | 'night' | 'day' | 'sheriff_election' | 'speak' | 'vote' | 'end';

export type RoleType = 'wolf' | 'civilian' | 'prophet' | 'guard' | 'hunter' | 'witch' | 'idiot' | 'unknown';

export type ScenePreset = 'six-player-dark' | 'nine-player-dark' | 'twelve-player-dark' | 'twelve-player-standard-dark';

export type GameMode = 'classic' | 'role_select';

export interface SceneConfig {
  preset: ScenePreset;
  name: string;
  description: string;
  playerCount: number;
  speakTimeoutSeconds: number;
  mode: GameMode;
  rules?: Record<string, unknown>;
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
  seatNumber: number;
  role: RoleType;
  isAI: boolean;
  isAlive: boolean;
  avatarUrl?: string;
  lastGuardTargetId?: string | null;
  isSheriff?: boolean;
  antidoteUsed?: boolean;
  poisonUsed?: boolean;
  isSpectator?: boolean;
  isIdiotRevealed?: boolean;
  lastProphetTargetId?: string | null;
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
  voterSeat?: number;
  targetId: string;
  targetSeat?: number;
}

export interface WolfTargetUpdate {
  wolfId: string;
  wolfSeat: number;
  targetId: string;
  targetSeat: number;
  message: string;
}

export interface VoteSummaryPayload {
  votes: VoteData[];
  eliminated: string | null;
}

export interface AnnounceMessage {
  id: string;
  content: string;
  time: string;
}

export interface ContributionEntry {
  playerId: string;
  playerName: string;
  role: string;
  faction: string;
  score: number;
  isAlive: boolean;
  isAI: boolean;
  details: string[];
}

export interface RoundEvent {
  type: 'night' | 'vote';
  round: number;
  killed_player_id?: string | null;
  guard_blocked?: boolean;
  prophet_checks?: Array<{ prophet_id: string; target_id: string; is_wolf: boolean }>;
  guard_saves?: Array<{ guard_id: string; target_id: string; saved: boolean }>;
  wolf_kills?: Array<{ wolf_id: string; target_id: string }>;
  votes?: Array<{ voterId: string; targetId: string }>;
  eliminated_id?: string | null;
}

export interface GameResultPayload {
  gameId: string;
  winnerFaction: string;
  currentRound: number;
  players: Player[];
  chats: ChatMessage[];
  announcements: string[];
  roundEvents: RoundEvent[];
  contributions: ContributionEntry[];
  mvp: ContributionEntry | null;
  svp: ContributionEntry | null;
}

export interface SpeakTurnPayload {
  currentSpeakerId: string | null;
  currentSpeakerName?: string;
  turnIndex?: number;
  turnCount?: number;
  deadline?: string;
  totalSeconds?: number;
  isLastWords?: boolean;
}

// 夜间行动请求载荷
export interface NightActionPayload {
  targetId: string;
  actionType: 'kill' | 'check';
}

// 夜间结果载荷（checkedResults 不再广播，预言家查验结果仅私发）
export interface NightResultPayload {
  killedPlayerId: string | null;
  guardedPlayerId?: string | null;
  guardBlocked?: boolean;
  witchSaved?: boolean;
  witchSavedPlayerId?: string | null;
  witchPoisonedPlayerId?: string | null;
  allKilledIds?: string[];
}

// 抢身份开始载荷
export interface RoleSelectStartPayload {
  availableRoles: string[];
  timeoutSeconds: number;
  message: string;
  deadline: string;
  totalSeconds: number;
}

// 抢身份选择载荷
export interface RoleSelectChoicePayload {
  role: string;
}

// 抢身份结果载荷
export interface RoleSelectResultPayload {
  assignments: Array<{ playerId: string; assignedRole: string }>;
  message: string;
}

// 警长竞选开始载荷
export interface SheriffElectStartPayload {
  phase: 'campaign' | 'speech' | 'vote';
  deadline: string;
  totalSeconds: number;
  candidateIds: string[];
}

// 警长竞选行动载荷（上警/退选）
export interface SheriffCampaignPayload {
  action: 'run' | 'withdraw' | 'register_done';
  playerId?: string;
  playerName?: string;
  candidateIds: string[];
}

// 警长竞选发言轮次
export interface SheriffSpeechTurnPayload {
  currentSpeakerId: string;
  currentSpeakerName: string;
  turnIndex: number;
  turnCount: number;
  deadline: string;
  totalSeconds: number;
  canWithdraw?: boolean;
}

// 警长竞选投票载荷
export interface SheriffVotePayload {
  candidateIds: string[];
  deadline: string;
  totalSeconds: number;
}

// 警长竞选结果
export interface SheriffElectResultPayload {
  sheriffId: string | null;
  isTie: boolean;
  message: string;
}

// 警长转让载荷
export interface SheriffTransferPayload {
  fromPlayerId: string;
  toPlayerId?: string;
  toPlayerName?: string;
  needsChoice?: boolean;
  candidateIds?: string[];
  deadline?: string;
  totalSeconds?: number;
}

// 发言方向选择请求载荷
export interface SpeakDirectionRequestPayload {
  sheriffId: string;
  deadline?: string;
  totalSeconds?: number;
}

// 发言方向选择载荷
export interface SpeakDirectionPayload {
  direction: 'left' | 'right';
}

// 狼人自爆载荷
export interface WolfSelfDestructPayload {
  playerId: string;
  playerName: string;
  playerRole: 'wolf';
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
  ownerPlayerId?: string;
  gameMode: GameMode;
  sheriffId?: string | null;
  sheriffCandidateIds?: string[];
  roomCode?: string;
  isSpectator?: boolean;
}

export interface SocketMessage<TPayload = Record<string, unknown>> {
  type:
    | 'room_update'
    | 'announce'
    | 'ai_speak'
    | 'player_speak'
    | 'vote_result'
    | 'vote_summary'
    | 'game_status'
    | 'role_info'
    | 'player_update'
    | 'game_over'
    | 'night_action'
    | 'night_result'
    | 'speak_turn'
    | 'wolf_target_update'
    | 'role_select_start'
    | 'role_select_choice'
    | 'role_select_result'
    | 'last_words'
    | 'sheriff_elect_start'
    | 'sheriff_campaign'
    | 'sheriff_speech_turn'
    | 'sheriff_vote'
    | 'sheriff_elect_result'
    | 'sheriff_transfer'
    | 'wolf_self_destruct'
    | 'speak_direction_request'
    | 'error';
  payload?: TPayload;
  timestamp?: string;
}
