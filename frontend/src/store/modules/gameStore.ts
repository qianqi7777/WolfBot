import { defineStore } from 'pinia';

import type {
  AnnounceMessage,
  RoomSettings,
  ChatMessage,
  GameResultPayload,
  GameSnapshot,
  GameStatus,
  NightResultPayload,
  Player,
  RoleType,
  VoteData,
  VoteSummaryPayload,
  AiConfigForm,
  WolfTargetUpdate,
  RoleSelectStartPayload,
  GameMode,
} from '@/types/game';

export interface GameState {
  gameId: string;
  gameStatus: GameStatus;
  currentRound: number;
  currentSpeakerId: string | null;
  started: boolean;
  winnerFaction: string | null;
  myRole: RoleType;
  myId: string;
  players: Player[];
  chatList: ChatMessage[];
  voteList: VoteData[];
  voteSummary: VoteSummaryPayload | null;
  announceList: AnnounceMessage[];
  result: GameResultPayload | null;
  nightActionRequired: boolean;
  nightResult: NightResultPayload | null;
  wolfTeammates: string[];
  wolfTargetUpdates: WolfTargetUpdate[];
  roomSettings: RoomSettings;
  ownerPlayerId: string | null;
  deadline: string | null;
  currentPhaseTimeout: number;
  // 抢身份相关
  roleSelectStart: RoleSelectStartPayload | null;
  mySelectedRole: string | null;
  gameMode: GameMode;
}

const SESSION_GAME_ID_KEY = 'wolfbot.gameId';
const SESSION_PLAYER_ID_KEY = 'wolfbot.playerId';
const AI_CONFIG_KEY = 'wolfbot.aiConfig';

/** 从 localStorage 恢复 AI 配置（非敏感字段） */
function loadAiConfig(): Partial<AiConfigForm> | null {
  if (typeof localStorage === 'undefined') return null;
  try {
    const raw = localStorage.getItem(AI_CONFIG_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** 保存 AI 配置到 localStorage（不含 apiKey） */
export function saveAiConfigToLocal(form: AiConfigForm): void {
  if (typeof localStorage === 'undefined') return;
  try {
    const toSave = {
      baseUrl: form.baseUrl,
      model: form.model,
      timeoutSeconds: form.timeoutSeconds,
      temperature: form.temperature,
      enableMock: form.enableMock,
    };
    localStorage.setItem(AI_CONFIG_KEY, JSON.stringify(toSave));
  } catch {
    // localStorage 不可用则忽略
  }
}

/** 获取上次保存的 AI 配置，合并到表单 */
export function getSavedAiConfig(): Partial<AiConfigForm> {
  return loadAiConfig() ?? {};
}

function createDefaultRoomSettings(): RoomSettings {
  return {
    scene: {
      preset: 'six-player-dark',
      name: '6人暗牌场',
      description: '2狼4好人，神职为预言家和守卫，暗牌局，无警长，节奏快。',
      playerCount: 6,
      speakTimeoutSeconds: 15,
      mode: 'classic',
    },
    ai: {
      baseUrl: '',
      model: 'gpt-4o-mini',
      timeoutSeconds: 20,
      temperature: 0.7,
      enableMock: true,
      hasApiKey: false,
    },
  };
}

function saveSession(gameId: string, playerId: string) {
  if (typeof localStorage === 'undefined') {
    return;
  }
  localStorage.setItem(SESSION_GAME_ID_KEY, gameId);
  localStorage.setItem(SESSION_PLAYER_ID_KEY, playerId);
}

function clearSession() {
  if (typeof localStorage === 'undefined') {
    return;
  }
  localStorage.removeItem(SESSION_GAME_ID_KEY);
  localStorage.removeItem(SESSION_PLAYER_ID_KEY);
}

function loadSession() {
  if (typeof localStorage === 'undefined') {
    return { gameId: '', playerId: '' };
  }
  return {
    gameId: localStorage.getItem(SESSION_GAME_ID_KEY) ?? '',
    playerId: localStorage.getItem(SESSION_PLAYER_ID_KEY) ?? '',
  };
}

export const useGameStore = defineStore('game', {
  state: (): GameState => ({
    gameId: '',
    gameStatus: 'waiting',
    currentRound: 1,
    currentSpeakerId: null,
    started: false,
    winnerFaction: null,
    myRole: 'unknown',
    myId: '',
    players: [],
    chatList: [],
    voteList: [],
    voteSummary: null,
    announceList: [],
    result: null,
    nightActionRequired: false,
    nightResult: null,
    wolfTeammates: [],
    wolfTargetUpdates: [],
    roomSettings: createDefaultRoomSettings(),
    ownerPlayerId: null,
    deadline: null,
    currentPhaseTimeout: 15,
    roleSelectStart: null,
    mySelectedRole: null,
    gameMode: 'classic',
  }),
  getters: {
    alivePlayers: (state) => state.players.filter((player) => player.isAlive),
    selfPlayer: (state) => state.players.find((player) => player.id === state.myId) ?? null,
    isOwner: (state) => state.ownerPlayerId !== null && state.myId === state.ownerPlayerId,
  },
  actions: {
    restoreSession() {
      const session = loadSession();
      if (session.gameId && !this.gameId) {
        this.gameId = session.gameId;
      }
      if (session.playerId && !this.myId) {
        this.myId = session.playerId;
      }
    },
    applySnapshot(snapshot: GameSnapshot, playerId = snapshot.playerId) {
      this.gameId = snapshot.gameId;
      this.myId = playerId;
      this.players = snapshot.players;
      this.gameStatus = snapshot.gameStatus;
      this.currentRound = snapshot.currentRound;
      this.currentSpeakerId = snapshot.currentSpeakerId ?? null;
      this.started = snapshot.started;
      this.winnerFaction = snapshot.winnerFaction;
      this.myRole = snapshot.myRole;
      this.nightActionRequired = snapshot.nightActionRequired ?? false;
      this.roomSettings = snapshot.roomSettings;
      if (snapshot.ownerPlayerId) this.ownerPlayerId = snapshot.ownerPlayerId;
      if ((snapshot as Record<string, unknown>).gameMode) {
        this.gameMode = (snapshot as Record<string, unknown>).gameMode as GameMode;
      }
      saveSession(this.gameId, this.myId);
    },
    setRoomSettings(roomSettings: RoomSettings) {
      this.roomSettings = roomSettings;
    },
    initGame(gameId: string, myId: string, players: Player[]) {
      this.gameId = gameId;
      this.myId = myId;
      this.players = players;
      this.chatList = [];
      this.voteList = [];
      this.voteSummary = null;
      this.announceList = [];
      this.gameStatus = 'waiting';
      this.currentRound = 1;
      this.currentSpeakerId = null;
      this.started = false;
      this.winnerFaction = null;
      this.result = null;
      this.roomSettings = createDefaultRoomSettings();
      saveSession(this.gameId, this.myId);
    },
    setMyRole(role: RoleType) {
      this.myRole = role;
    },
    setGameStatus(status: GameStatus) {
      this.gameStatus = status;
    },
    setCurrentRound(round: number) {
      this.currentRound = round;
    },
    setCurrentSpeakerId(playerId: string | null) {
      this.currentSpeakerId = playerId;
    },
    setNightActionRequired(flag: boolean) {
      this.nightActionRequired = flag;
    },
    setWolfTeammates(teammates: string[]) {
      this.wolfTeammates = teammates;
    },
    addWolfTargetUpdate(update: WolfTargetUpdate) {
      // 同一狼人更新时覆盖旧记录
      this.wolfTargetUpdates = [
        ...this.wolfTargetUpdates.filter((u) => u.wolfId !== update.wolfId),
        update,
      ];
    },
    setNightResult(result: NightResultPayload) {
      this.nightResult = result;
    },
    resetNightActions() {
      this.nightActionRequired = false;
      this.nightResult = null;
      this.wolfTeammates = [];
      this.wolfTargetUpdates = [];
    },
    clearVotes() {
      this.voteList = [];
    },
    addChatMessage(message: ChatMessage) {
      this.chatList.push(message);
    },
    addVote(vote: VoteData) {
      this.voteList.push(vote);
    },
    setVoteSummary(summary: VoteSummaryPayload) {
      this.voteSummary = summary;
    },
    setDeadline(deadline: string | null) {
      this.deadline = deadline;
    },
    setCurrentPhaseTimeout(timeout: number) {
      this.currentPhaseTimeout = timeout;
    },
    setRoleSelectStart(payload: RoleSelectStartPayload) {
      this.roleSelectStart = payload;
    },
    setMySelectedRole(role: string | null) {
      this.mySelectedRole = role;
    },
    setGameMode(mode: GameMode) {
      this.gameMode = mode;
    },
    addAnnounce(content: string) {
      this.announceList.push({
        id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
        content,
        time: new Date().toISOString(),
      });
    },
    updatePlayerStatus(playerId: string, isAlive: boolean) {
      const player = this.players.find((item) => item.id === playerId);
      if (player) {
        player.isAlive = isAlive;
      }
    },
    setResult(result: GameResultPayload) {
      this.result = result;
      this.winnerFaction = result.winnerFaction;
      this.currentRound = result.currentRound;
      this.currentSpeakerId = null;
      this.players = result.players;
      this.announceList = result.announcements.map((content, index) => ({
        id: `result-${index}`,
        content,
        time: new Date().toISOString(),
      }));
      this.chatList = result.chats;
      this.gameStatus = 'end';
    },
    resetGame() {
      this.gameId = '';
      this.gameStatus = 'waiting';
      this.currentRound = 1;
      this.currentSpeakerId = null;
      this.started = false;
      this.winnerFaction = null;
      this.myRole = 'unknown';
      this.myId = '';
      this.players = [];
      this.chatList = [];
      this.voteList = [];
      this.voteSummary = null;
      this.announceList = [];
      this.result = null;
      this.nightActionRequired = false;
      this.nightResult = null;
      this.wolfTeammates = [];
      this.wolfTargetUpdates = [];
      this.roomSettings = createDefaultRoomSettings();
      this.ownerPlayerId = null;
      this.deadline = null;
      this.currentPhaseTimeout = 15;
      this.roleSelectStart = null;
      this.mySelectedRole = null;
      this.gameMode = 'classic';
      clearSession();
    },
  },
});
