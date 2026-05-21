<template>
  <!-- 角色图标组件：根据 RoleType 渲染对应 SVG -->
  <div class="role-icon" :style="{ width: sizePx, height: sizePx }">
    <img :src="iconUrl" :alt="roleLabel" class="role-icon-img" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { RoleType } from '@/types/game';
import { ROLE_LABELS } from '@/utils/constants';
import roleWolf from '@/assets/avatars/role-wolf.svg';
import roleCivilian from '@/assets/avatars/role-civilian.svg';
import roleProphet from '@/assets/avatars/role-prophet.svg';
import roleGuard from '@/assets/avatars/role-guard.svg';
import roleHunter from '@/assets/avatars/role-hunter.svg';
import roleWitch from '@/assets/avatars/role-witch.svg';
import roleIdiot from '@/assets/avatars/role-idiot.svg';
import roleUnknown from '@/assets/avatars/role-unknown.svg';

/** 角色类型到 SVG 文件的映射 */
const ROLE_ICON_MAP: Record<RoleType, string> = {
  wolf: roleWolf,
  civilian: roleCivilian,
  prophet: roleProphet,
  guard: roleGuard,
  hunter: roleHunter,
  witch: roleWitch,
  idiot: roleIdiot,
  unknown: roleUnknown,
};

const props = withDefaults(defineProps<{
  /** 角色类型 */
  role: RoleType;
  /** 图标尺寸（px），默认 40 */
  size?: number;
}>(), {
  size: 40,
});

/** 图标 URL */
const iconUrl = computed(() => ROLE_ICON_MAP[props.role] || roleUnknown);

/** 角色名称 */
const roleLabel = computed(() => ROLE_LABELS[props.role]);

/** 尺寸 px 值 */
const sizePx = computed(() => `${props.size}px`);
</script>

<style scoped>
.role-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.role-icon-img {
  width: 100%;
  height: 100%;
  color: var(--text-primary);
}
</style>
