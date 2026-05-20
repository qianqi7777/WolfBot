<template>
  <el-card v-if="roleSelectData" shadow="always" class="role-select-card">
    <template #header>
      <div class="role-select-header">
        <span>抢身份</span>
        <CountdownTimer
          :deadline="roleSelectData.deadline || null"
          :total-seconds="roleSelectData.totalSeconds"
        />
      </div>
    </template>
    <el-alert
      :title="roleSelectData.message"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 12px"
    />
    <div class="role-select-options">
      <div
        v-for="role in availableRoles"
        :key="role.id"
        class="role-option"
        :class="{ 'role-option-selected': mySelectedRole === role.id }"
        @click="selectRole(role.id)"
      >
        <div class="role-icon">{{ role.icon }}</div>
        <div class="role-info">
          <div class="role-name">{{ role.name }}</div>
          <div class="role-desc">{{ role.desc }}</div>
        </div>
        <el-tag v-if="mySelectedRole === role.id" type="success" size="small">已选择</el-tag>
      </div>
    </div>
    <div class="role-select-actions">
      <el-button
        type="primary"
        :disabled="!mySelectedRole"
        @click="confirmSelection"
      >
        确认选择
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import CountdownTimer from './CountdownTimer.vue';
import { useGameStore } from '@/store/modules/gameStore';
import { useGameSocket } from '@/hooks/useGameSocket';
import type { RoleType } from '@/types/game';

const store = useGameStore();
const { send } = useGameSocket();

const roleSelectData = computed(() => store.roleSelectStart);
const mySelectedRole = computed(() => store.mySelectedRole);

// 角色信息映射
const ROLE_INFO: Record<string, { id: string; name: string; icon: string; desc: string }> = {
  wolf: { id: 'wolf', name: '狼人', icon: '🐺', desc: '夜间袭击，白天伪装' },
  civilian: { id: 'civilian', name: '平民', icon: '👤', desc: '无特殊技能，靠推理找狼' },
  prophet: { id: 'prophet', name: '预言家', icon: '🔮', desc: '每晚查验一名玩家身份' },
  guard: { id: 'guard', name: '守卫', icon: '🛡️', desc: '每晚守护一名玩家' },
  hunter: { id: 'hunter', name: '猎人', icon: '🎯', desc: '死亡时可开枪带走一人' },
  witch: { id: 'witch', name: '女巫', icon: '🧪', desc: '一瓶解药一瓶毒药各一次' },
  idiot: { id: 'idiot', name: '白痴', icon: '🃏', desc: '被投票放逐时免疫出局' },
};

const availableRoles = computed(() => {
  if (!roleSelectData.value) return [];
  // 去重并生成选项
  const seen = new Set<string>();
  const roles: Array<{ id: string; name: string; icon: string; desc: string }> = [];
  for (const r of roleSelectData.value.availableRoles) {
    if (!seen.has(r)) {
      seen.add(r);
      const info = ROLE_INFO[r] || { id: r, name: r, icon: '❓', desc: '' };
      roles.push(info);
    }
  }
  return roles;
});

const selectRole = (roleId: string) => {
  store.setMySelectedRole(roleId);
};

const confirmSelection = () => {
  if (!mySelectedRole.value) return;
  send({
    type: 'role_select_choice',
    payload: { role: mySelectedRole.value },
  });
};
</script>

<style scoped>
.role-select-card {
  animation: fadeIn 0.3s ease;
}

.role-select-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.role-select-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.role-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 2px solid var(--el-border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.role-option:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.role-option-selected {
  border-color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}

.role-icon {
  font-size: 24px;
  min-width: 32px;
  text-align: center;
}

.role-info {
  flex: 1;
}

.role-name {
  font-weight: bold;
  font-size: 14px;
}

.role-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 2px;
}

.role-select-actions {
  display: flex;
  justify-content: flex-end;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
