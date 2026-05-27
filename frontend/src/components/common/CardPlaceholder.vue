<template>
  <!-- 牌面占位卡：图片缺失时使用 -->
  <div
    class="card-placeholder"
    :class="[`size-${size}`, `faction-${faction}`]"
    :title="hint"
  >
    <!-- 顶部：角色名 -->
    <div class="card-name">{{ roleLabel }}</div>

    <!-- 中部：现有 SVG 图标 -->
    <div class="card-icon-area">
      <RoleIcon :role="role" :size="iconSize" />
    </div>

    <!-- 底部：阵营 + 技能描述 -->
    <div class="card-footer">
      <div class="faction-tag">{{ factionLabel }}</div>
      <div v-if="size === 'large'" class="skill-desc">{{ skillDesc }}</div>
    </div>

    <!-- 待补图角标（仅开发环境） -->
    <div v-if="showDevHint" class="dev-hint">📷 待补图</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { RoleType } from '@/types/game';
import { ROLE_LABELS, ROLE_FACTION, FACTION_LABELS, ROLE_SKILL_DESC } from '@/utils/constants';
import RoleIcon from './RoleIcon.vue';

const props = withDefaults(defineProps<{
  role: RoleType;
  /** 尺寸：small=顶栏小卡, large=翻牌弹窗大卡 */
  size?: 'small' | 'large';
}>(), {
  size: 'large',
});

const roleLabel = computed(() => ROLE_LABELS[props.role]);
const faction = computed(() => ROLE_FACTION[props.role]);
const factionLabel = computed(() => FACTION_LABELS[faction.value]);
const skillDesc = computed(() => ROLE_SKILL_DESC[props.role]);
const iconSize = computed(() => (props.size === 'large' ? 120 : 40));
const hint = computed(() => `${roleLabel.value} — 缺少 card-${props.role}.webp`);
const showDevHint = computed(() => import.meta.env.DEV && props.size === 'large');
</script>

<style scoped>
.card-placeholder {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(135deg, var(--bg-card) 0%, rgba(128, 128, 128, 0.15) 100%);
  border: 2px solid var(--border-color);
  border-radius: 12px;
  box-sizing: border-box;
  user-select: none;
  overflow: hidden;
}

.card-placeholder.size-small {
  width: 56px;
  height: 84px;
  padding: 4px;
  gap: 2px;
}

.card-placeholder.size-large {
  width: 100%;
  max-width: 280px;
  aspect-ratio: 2 / 3;
  padding: 16px;
  gap: 12px;
}

/* 阵营色边框 */
.card-placeholder.faction-wolf {
  border-color: var(--faction-wolf, #ef4444);
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.25);
}
.card-placeholder.faction-civilian {
  border-color: var(--faction-civilian, #22c55e);
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.2);
}

.card-name {
  font-weight: 700;
  text-align: center;
  color: var(--text-primary);
  letter-spacing: 0.05em;
}
.size-small .card-name { font-size: 11px; }
.size-large .card-name { font-size: 22px; }

.card-icon-area {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.card-footer {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.faction-tag {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.25);
  color: #fff;
}
.faction-wolf .faction-tag { background: var(--faction-wolf, #ef4444); }
.faction-civilian .faction-tag { background: var(--faction-civilian, #22c55e); }

.skill-desc {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.5;
  padding: 0 4px;
}

.dev-hint {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.6);
  color: #ffeb3b;
  letter-spacing: 0.05em;
}
</style>
