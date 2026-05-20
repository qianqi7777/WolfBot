import type { GameStatus, RoleType, ScenePreset } from '@/types/game';

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
  hunter: '猎人',
  witch: '女巫',
  unknown: '未知',
};

export const SCENE_PRESET_OPTIONS: Array<{
  value: ScenePreset;
  label: string;
  description: string;
  playerCount: number;
}> = [
  {
    value: 'six-player-dark',
    label: '6人暗牌场',
    description: '2狼4好人，神职为预言家和守卫，暗牌局，无警长，节奏快。',
    playerCount: 6,
  },
  {
    value: 'nine-player-dark',
    label: '9人暗牌场',
    description: '3狼6好人，神职为预言家、守卫、猎人，暗牌局，无警长。',
    playerCount: 9,
  },
  {
    value: 'twelve-player-dark',
    label: '12人暗牌场',
    description: '4狼8好人，神职为预言家、守卫、女巫、猎人，暗牌局，有警长。',
    playerCount: 12,
  },
];

export const DEFAULT_VOTE_LIMIT = 60;

// 场景规则标签
export const WIN_CONDITION_LABELS: Record<string, string> = {
  slaughter_edge: '屠边（屠民/屠神）',
};

export const SPEAK_ORDER_LABELS: Record<string, string> = {
  by_seat: '按座位号',
  by_random: '随机顺序',
  sheriff_first: '警长发言',
};

export const VOTE_TIE_LABELS: Record<string, string> = {
  no_elimination: '平票无人出局',
  re_vote: '平票重新投票',
  both_eliminated: '平票双双出局',
};
