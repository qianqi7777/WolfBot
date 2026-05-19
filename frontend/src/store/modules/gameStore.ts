import { defineStore } from 'pinia';

import type {
  AnnounceMessage,
  ChatMessage,
  GameResultPayload,
  GameSnapshot,
  GameStatus,
  Player,
  RoleType,
  VoteData,
} from '@/types/game';

export interface GameState {
  gameId: string;
  gameStatus: GameStatus;
  currentRound: number;
  started: boolean;
  winnerFaction: string | null;
  myRole: RoleType;
  myId: string;
  players: Player[];
  chatList: ChatMessage[];
  voteList: VoteData[];
  announceList: AnnounceMessage[];
  result: GameResultPayload | null;
}

const SESSION_GAME_ID_KEY = 'wolfbot.gameId';
const SESSION_PLAYER_ID_KEY = 'wolfbot.playerId';

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
    started: false,
    winnerFaction: null,
    myRole: 'unknown',
    myId: '',
    players: [],
    chatList: [],
    voteList: [],
    announceList: [],
    result: null,
  }),
  getters: {
    alivePlayers: (state) => state.players.filter((player) => player.isAlive),
    selfPlayer: (state) => state.players.find((player) => player.id === state.myId) ?? null,
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
      this.started = snapshot.started;
      this.winnerFaction = snapshot.winnerFaction;
      this.myRole = snapshot.myRole;
      saveSession(this.gameId, this.myId);
    },
    initGame(gameId: string, myId: string, players: Player[]) {
      this.gameId = gameId;
      this.myId = myId;
      this.players = players;
      this.chatList = [];
      this.voteList = [];
      this.announceList = [];
      this.gameStatus = 'waiting';
      this.currentRound = 1;
      this.started = false;
      this.winnerFaction = null;
      this.result = null;
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
    addChatMessage(message: ChatMessage) {
      this.chatList.push(message);
    },
    addVote(vote: VoteData) {
      this.voteList.push(vote);
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
      this.started = false;
      this.winnerFaction = null;
      this.myRole = 'unknown';
      this.myId = '';
      this.players = [];
      this.chatList = [];
      this.voteList = [];
      this.announceList = [];
      this.result = null;
      clearSession();
    },
  },
});
