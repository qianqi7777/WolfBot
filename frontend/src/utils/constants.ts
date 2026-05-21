import type { GameStatus, RoleType, ScenePreset } from '@/types/game';

export const GAME_STATUS_LABELS: Record<GameStatus, string> = {
  waiting: '等待开局',
  role_select: '抢身份',
  night: '夜间阶段',
  day: '白天阶段',
  sheriff_election: '警长竞选',
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
  idiot: '白痴',
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
  {
    value: 'twelve-player-standard-dark',
    label: '12人标准暗牌场（预女猎白）',
    description: '4狼8好人，神职为预言家、女巫、猎人、白痴，屠边规则。',
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

// 阵营定义：每个角色所属阵营
export const ROLE_FACTION: Record<RoleType, 'wolf' | 'civilian'> = {
  wolf: 'wolf',
  civilian: 'civilian',
  prophet: 'civilian',
  guard: 'civilian',
  hunter: 'civilian',
  witch: 'civilian',
  idiot: 'civilian',
  unknown: 'civilian',
};

// 阵营标签
export const FACTION_LABELS: Record<string, string> = {
  wolf: '狼人阵营',
  civilian: '好人阵营',
};

// 角色技能简述
export const ROLE_SKILL_DESC: Record<RoleType, string> = {
  wolf: '夜间与同伴协商击杀一名玩家',
  civilian: '通过发言和投票找出狼人',
  prophet: '每晚可查验一名玩家的身份',
  guard: '每晚可守护一名玩家免受袭击',
  hunter: '死亡时可以开枪带走一名玩家',
  witch: '拥有一瓶解药和一瓶毒药',
  idiot: '被投票放逐时可翻牌免疫出局',
  unknown: '身份尚未分配',
};
