/**
 * 背景图工具
 *
 * 通过 import.meta.glob 动态加载 assets/backgrounds/ 目录下的 webp，
 * 生成响应式 image-set CSS 字符串。文件缺失时返回 null，让 CSS 回退到渐变。
 */
const bgModules = import.meta.glob('@/assets/backgrounds/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>;

function lookup(filename: string): string | null {
  const entry = Object.entries(bgModules).find(([path]) => path.endsWith(`/${filename}`));
  return entry ? entry[1] : null;
}

export type BackgroundScene = 'day' | 'night' | 'home' | 'result-civilian' | 'result-wolf';

const warned = new Set<string>();

function warnOnce(filename: string): void {
  if (import.meta.env.DEV && !warned.has(filename)) {
    warned.add(filename);
    console.warn(`[backgroundImage] 缺少背景文件: src/assets/backgrounds/${filename}（已 fallback 到 CSS 渐变）`);
  }
}

/**
 * 返回某个场景的桌面端 1x url（用于 preload 或 fallback）
 */
export function getBackgroundUrl(scene: BackgroundScene): string | null {
  const url = lookup(`bg-${scene}.webp`);
  if (!url) warnOnce(`bg-${scene}.webp`);
  return url;
}

/**
 * 返回某个场景的移动端 url
 */
export function getMobileBackgroundUrl(scene: BackgroundScene): string | null {
  return lookup(`bg-${scene}-mobile.webp`);
}

/**
 * 返回某个场景的 2x url
 */
export function get2xBackgroundUrl(scene: BackgroundScene): string | null {
  return lookup(`bg-${scene}@2x.webp`);
}

/**
 * 生成 image-set CSS 字符串（含 1x/2x），无图返回 null
 * 使用时配合 @media (max-width: 768px) 切换 mobile 变体
 */
export function getDesktopImageSet(scene: BackgroundScene): string | null {
  const url1x = getBackgroundUrl(scene);
  if (!url1x) return null;
  const url2x = get2xBackgroundUrl(scene);
  if (url2x) {
    return `image-set(url("${url1x}") 1x, url("${url2x}") 2x)`;
  }
  return `url("${url1x}")`;
}

/**
 * 生成移动端 image-set
 */
export function getMobileImageSet(scene: BackgroundScene): string | null {
  const mobileUrl = getMobileBackgroundUrl(scene);
  if (mobileUrl) return `url("${mobileUrl}")`;
  // 移动端缺图时 fallback 到桌面 1x
  return getDesktopImageSet(scene);
}
