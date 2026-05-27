/**
 * 角色牌面图片工具
 *
 * 通过 import.meta.glob 动态加载 assets/cards/ 目录下的 webp，
 * 文件存在则返回 URL，缺失则返回 null（由组件 fallback 到占位卡）。
 */
import type { RoleType } from '@/types/game';

const cardModules = import.meta.glob('@/assets/cards/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

function lookup(filename: string): string | null {
  const entry = Object.entries(cardModules).find(([path]) => path.endsWith(`/${filename}`));
  return entry ? entry[1] : null;
}

const ROLE_TO_CARD: Record<RoleType, string> = {
  wolf: 'card-wolf.webp',
  civilian: 'card-civilian.webp',
  prophet: 'card-prophet.webp',
  guard: 'card-guard.webp',
  hunter: 'card-hunter.webp',
  witch: 'card-witch.webp',
  idiot: 'card-idiot.webp',
  unknown: '',
};

const warned = new Set<string>();

/**
 * 获取指定角色的牌面图片 URL
 * @param role 角色类型
 * @returns 图片 URL，若文件不存在返回 null
 */
export function getRoleCard(role: RoleType): string | null {
  const filename = ROLE_TO_CARD[role];
  if (!filename) return null;
  const url = lookup(filename);
  if (!url && import.meta.env.DEV && !warned.has(filename)) {
    warned.add(filename);
    console.warn(`[cardImage] 缺少牌面文件: src/assets/cards/${filename}（已 fallback 到占位卡）`);
  }
  return url;
}

/**
 * 获取牌背图片 URL（用于翻牌动画）
 * @returns 牌背 URL，文件不存在返回 null
 */
export function getCardBack(): string | null {
  const url = lookup('card-back.webp');
  if (!url && import.meta.env.DEV && !warned.has('card-back.webp')) {
    warned.add('card-back.webp');
    console.warn('[cardImage] 缺少牌背文件: src/assets/cards/card-back.webp（已 fallback 到 CSS 牌背）');
  }
  return url;
}
