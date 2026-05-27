/**
 * 用户偏好设置 hook
 *
 * 负责存取 localStorage 里的 UI 偏好（背景图开关、动画开关），
 * 并桥接系统级 prefers-reduced-motion 媒体查询。
 *
 * 数据流：localStorage 持久化 → 全局响应式 ref → 组件订阅。
 * 多个组件 useUserPreferences() 时共享同一份 state（模块级 ref）。
 */
import { ref, computed, watch } from 'vue';

const STORAGE_KEY = 'wolfbot.userPreferences.v1';

interface StoredPreferences {
  enableBackground: boolean;
  enableAnimations: boolean;
}

const defaults: StoredPreferences = {
  enableBackground: true,
  enableAnimations: true,
};

function readFromStorage(): StoredPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...defaults };
    const parsed = JSON.parse(raw) as Partial<StoredPreferences>;
    return {
      enableBackground: parsed.enableBackground ?? defaults.enableBackground,
      enableAnimations: parsed.enableAnimations ?? defaults.enableAnimations,
    };
  } catch {
    return { ...defaults };
  }
}

function writeToStorage(value: StoredPreferences): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    /* 存储失败时静默忽略，不影响 UI */
  }
}

// 模块级单例 state，多组件共享
const initial = readFromStorage();
const enableBackground = ref(initial.enableBackground);
const enableAnimations = ref(initial.enableAnimations);

// 系统级 prefers-reduced-motion 监听
const prefersReducedMotion = ref(false);
if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  prefersReducedMotion.value = mq.matches;
  const onChange = (e: MediaQueryListEvent) => {
    prefersReducedMotion.value = e.matches;
  };
  if (typeof mq.addEventListener === 'function') {
    mq.addEventListener('change', onChange);
  }
}

// 任何变更都持久化
watch(
  [enableBackground, enableAnimations],
  ([bg, anim]) => {
    writeToStorage({ enableBackground: bg, enableAnimations: anim });
  },
);

export function useUserPreferences() {
  /** 是否启用动画的最终值：用户开关 && 系统未要求减少动效 */
  const animationsEffective = computed(
    () => enableAnimations.value && !prefersReducedMotion.value,
  );

  return {
    enableBackground,
    enableAnimations,
    prefersReducedMotion,
    animationsEffective,
  };
}
