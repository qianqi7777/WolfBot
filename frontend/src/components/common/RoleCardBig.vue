<template>
  <!--
    立绘式大牌：用于翻牌弹窗与结算页
    - 有牌面图：渲染立绘 + 名字 + 阵营 + 技能描述
    - 缺图时 fallback 到 CardPlaceholder
  -->
  <div
    v-if="cardUrl"
    class="role-card-big"
    :class="[`faction-${faction}`, { highlight: highlight }]"
  >
    <img :src="cardUrl" :alt="roleLabel" class="card-img" loading="lazy" />
    <div class="card-overlay">
      <div class="card-top">
        <span class="role-name">{{ roleLabel }}</span>
        <span class="faction-tag">{{ factionLabel }}</span>
      </div>
      <div class="card-bottom">{{ skillDesc }}</div>
    </div>
  </div>
  <CardPlaceholder v-else :role="role" size="large" />
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { RoleType } from '@/types/game';
import { ROLE_LABELS, ROLE_FACTION, FACTION_LABELS, ROLE_SKILL_DESC } from '@/utils/constants';
import { getRoleCard } from '@/utils/cardImage';
import CardPlaceholder from './CardPlaceholder.vue';

const props = withDefaults(defineProps<{
  role: RoleType;
  /** 是否使用胜方光晕高亮（结算页用） */
  highlight?: boolean;
}>(), {
  highlight: false,
});

const cardUrl = computed(() => getRoleCard(props.role));
const roleLabel = computed(() => ROLE_LABELS[props.role]);
const faction = computed(() => ROLE_FACTION[props.role]);
const factionLabel = computed(() => FACTION_LABELS[faction.value]);
const skillDesc = computed(() => ROLE_SKILL_DESC[props.role]);
</script>

<style scoped>
.role-card-big {
  position: relative;
  width: 100%;
  max-width: 280px;
  aspect-ratio: 2 / 3;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid var(--border-color);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  transition: box-shadow 0.4s ease, transform 0.3s ease;
}

.role-card-big.faction-wolf {
  border-color: var(--faction-wolf, #ef4444);
}
.role-card-big.faction-civilian {
  border-color: var(--faction-civilian, #22c55e);
}

.role-card-big.highlight.faction-wolf {
  box-shadow: 0 0 28px rgba(239, 68, 68, 0.75), 0 0 8px rgba(239, 68, 68, 0.5);
}
.role-card-big.highlight.faction-civilian {
  box-shadow: 0 0 28px rgba(34, 197, 94, 0.75), 0 0 8px rgba(34, 197, 94, 0.5);
}

.card-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.card-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 12px;
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.55) 0%,
    rgba(0, 0, 0, 0) 30%,
    rgba(0, 0, 0, 0) 65%,
    rgba(0, 0, 0, 0.78) 100%
  );
  color: #fff;
  pointer-events: none;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.role-name {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.7);
}

.faction-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.55);
}
.faction-wolf .faction-tag { background: var(--faction-wolf, #ef4444); }
.faction-civilian .faction-tag { background: var(--faction-civilian, #22c55e); }

.card-bottom {
  font-size: 13px;
  line-height: 1.5;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.85);
}
</style>
