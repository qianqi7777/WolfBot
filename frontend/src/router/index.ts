import { createRouter, createWebHistory } from 'vue-router';

import { getGame } from '@/api/gameApi';
import { useGameStore } from '@/store/modules/gameStore';

const HomeView = () => import('@/views/HomeView.vue');
const GameRoom = () => import('@/views/GameRoom.vue');
const GamePlay = () => import('@/views/GamePlay.vue');
const GameResult = () => import('@/views/GameResult.vue');

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView },
    { path: '/room/:gameId', name: 'room', component: GameRoom, props: true },
    { path: '/game/:gameId', name: 'game', component: GamePlay, props: true },
    { path: '/result/:gameId', name: 'result', component: GameResult, props: true },
  ],
});

router.beforeEach(async (to) => {
  const store = useGameStore();
  if (to.name === 'room' || to.name === 'game' || to.name === 'result') {
    const gameId = typeof to.params.gameId === 'string' ? to.params.gameId : '';
    if (!gameId) {
      return { name: 'home' };
    }

    if (!store.gameId || store.gameId !== gameId) {
      try {
        store.restoreSession();
        store.applySnapshot(await getGame(gameId), store.myId || undefined);
      } catch {
        return { name: 'home' };
      }
    }
  }
  return true;
});

export default router;
