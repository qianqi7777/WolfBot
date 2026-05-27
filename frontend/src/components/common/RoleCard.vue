<template>
  <!-- 角色卡片：图标+阵营+技能描述（顶栏小卡） -->
  <div class="role-card-v2" :class="{ 'role-unknown': role === 'unknown' }">
    <template v-if="role === 'unknown'">
      <!-- 身份未分配占位 -->
      <RoleIcon :role="role" :size="48" />
      <div class="role-info">
        <div class="role-name">身份未分配</div>
        <div class="role-desc">等待游戏开始后分配角色</div>
      </div>
    </template>
    <template v-else>
      <!-- 有牌面：立绘小卡 + 信息；无牌面：原 SVG 图标 + 信息 -->
      <div class="role-visual">
        <img
          v-if="cardUrl"
          :src="cardUrl"
          :alt="roleLabel"
          class="role-card-thumb"
          loading="lazy"
        />
        <RoleIcon v-else :role="role" :size="48" />
      </div>
      <div class="role-info">
        <div class="role-name">{{ roleLabel }}</div>
        <!-- 阵营标签 -->
        <el-tag
          :type="faction === 'wolf' ? 'danger' : 'success'"
          size="small"
          class="role-faction-tag"
        >
          {{ factionLabel }}
        </el-tag>
        <!-- 技能描述 -->
        <div class="role-desc">{{ skillDesc }}</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { RoleType } from '@/types/game';
import { ROLE_LABELS, ROLE_FACTION, FACTION_LABELS, ROLE_SKILL_DESC } from '@/utils/constants';
import { getRoleCard } from '@/utils/cardImage';
import RoleIcon from './RoleIcon.vue';

const props = defineProps<{
  /** 当前角色 */
  role: RoleType;
}>();

/** 牌面图片 URL（缺图时为 null，自动回退到 SVG 图标） */
const cardUrl = computed(() => getRoleCard(props.role));

/** 角色名称 */
const roleLabel = computed(() => ROLE_LABELS[props.role]);

/** 所属阵营 */
const faction = computed(() => ROLE_FACTION[props.role]);

/** 阵营标签 */
const factionLabel = computed(() => FACTION_LABELS[faction.value]);

/** 技能描述 */
const skillDesc = computed(() => ROLE_SKILL_DESC[props.role]);
</script>

<style scoped>
.role-card-v2 {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  transition: background 0.5s ease, border-color 0.5s ease;
}

.role-unknown {
  opacity: 0.7;
}

.role-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.role-card-thumb {
  width: 48px;
  height: 72px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--border-color);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
}

.role-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.role-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.role-faction-tag {
  width: fit-content;
}

.role-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}
</style>
