/**
 * 翻牌弹窗触发 hook
 *
 * 提供全局唯一队列，所有翻牌请求依次入队，弹窗按队列顺序播放，
 * 避免并发场景（如同一帧白痴翻牌 + 狼自爆）相互覆盖。
 *
 * 数据流：业务方调用 reveal({...}) → 入队 → RoleRevealModal 取队首播放 →
 * 动画结束/超时/点击关闭 → 出队 → 下一张。
 */
import { ref, computed } from 'vue';
import type { RoleType } from '@/types/game';

export type RevealMode = 'private' | 'public';

export interface RevealRequest {
  /** 角色 */
  role: RoleType;
  /** 显示给玩家看的名称，例如 "3号(玩家A)"；未提供时弹窗仅显示角色信息 */
  name?: string;
  /** 模式：private=仅自己看到的隐私翻牌；public=全场公开翻牌 */
  mode: RevealMode;
  /** 标题文字覆盖，默认根据 mode 生成 */
  title?: string;
  /** 自动关闭时长（ms），0 表示需手动关闭。默认 3500 */
  autoCloseMs?: number;
}

const queue = ref<RevealRequest[]>([]);

export function useRoleReveal() {
  /** 入队一个翻牌请求 */
  function reveal(req: RevealRequest): void {
    queue.value.push(req);
  }

  /** 弹窗组件消费完队首后调用 */
  function dismissCurrent(): void {
    if (queue.value.length > 0) {
      queue.value.shift();
    }
  }

  /** 清空（重开局时使用） */
  function clear(): void {
    queue.value = [];
  }

  /** 当前队首（响应式），由 modal 组件订阅 */
  const current = computed(() => (queue.value.length > 0 ? queue.value[0] : null));

  return {
    reveal,
    dismissCurrent,
    clear,
    current,
  };
}
