import { defineStore } from 'pinia';

import type { AnnounceMessage, ChatMessage, GameStatus, Player, RoleType, VoteData } from '@/types/game';

export interface GameState {
  gameId: string;
  gameStatus: GameStatus;
  myRole: RoleType;
  myId: string;
  players: Player[];
  chatList: ChatMessage[];
  voteList: VoteData[];
  announceList: AnnounceMessage[];
}

export const useGameStore = defineStore('game', {
  state: (): GameState => ({
    gameId: '',
    gameStatus: 'waiting',
    myRole: 'unknown',
    myId: '',
    players: [],
    chatList: [],
    voteList: [],
    announceList: [],
  }),
  getters: {
    alivePlayers: (state) => state.players.filter((player) => player.isAlive),
  },
  actions: {
    initGame(gameId: string, myId: string, players: Player[]) {
      this.gameId = gameId;
      this.myId = myId;
      this.players = players;
      this.chatList = [];
      this.voteList = [];
      this.announceList = [];
      this.gameStatus = 'waiting';
    },
    setMyRole(role: RoleType) {
      this.myRole = role;
    },
    setGameStatus(status: GameStatus) {
      this.gameStatus = status;
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
    resetGame() {
      this.gameId = '';
      this.gameStatus = 'waiting';
      this.myRole = 'unknown';
      this.myId = '';
      this.players = [];
      this.chatList = [];
      this.voteList = [];
      this.announceList = [];
    },
  },
});
