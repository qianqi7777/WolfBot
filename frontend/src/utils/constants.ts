import type { GameStatus, RoleType } from '@/types/game';

export const GAME_STATUS_LABELS: Record<GameStatus, string> = {
  waiting: '等待开局',
  night: '夜间阶段',
  day: '白天阶段',
  speak: '发言阶段',
  vote: '投票阶段',
  end: '对局结束',
};

export const ROLE_LABELS: Record<RoleType, string> = {
  wolf: '狼人',
  civilian: '平民',
  prophet: '预言家',
  guard: '守卫',
  unknown: '未知',
};

export const DEFAULT_VOTE_LIMIT = 60;
