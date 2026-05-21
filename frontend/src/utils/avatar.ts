/**
 * 头像计算工具函数
 * 统一管理玩家头像的获取逻辑
 */
import avatarHuman from '@/assets/avatars/avatar-human.svg';
import avatarAI from '@/assets/avatars/avatar-ai.svg';
import type { Player } from '@/types/game';

/**
 * 获取玩家头像 URL
 * 优先级：自定义 avatarUrl > AI 默认头像 > 真人默认头像
 * @param player 玩家数据
 * @returns 头像 URL 字符串
 */
export function getPlayerAvatar(player: Player): string {
  if (player.avatarUrl) return player.avatarUrl;
  return player.isAI ? avatarAI : avatarHuman;
}

/**
 * 获取默认头像（按 isAI 区分）
 * @param isAI 是否为 AI 玩家
 * @returns 默认头像 URL 字符串
 */
export function getDefaultAvatar(isAI: boolean): string {
  return isAI ? avatarAI : avatarHuman;
}
