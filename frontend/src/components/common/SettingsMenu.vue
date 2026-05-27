<template>
  <!-- 顶栏齿轮入口：背景图 / 翻牌动画开关 -->
  <el-popover
    placement="bottom-end"
    :width="240"
    trigger="click"
    popper-class="settings-menu-popper"
  >
    <template #reference>
      <button class="settings-trigger" title="界面设置" aria-label="界面设置">
        <span class="gear-icon">⚙</span>
      </button>
    </template>
    <div class="settings-menu">
      <div class="menu-title">界面设置</div>
      <div class="menu-row">
        <span class="row-label">背景配图</span>
        <el-switch v-model="enableBackground" />
      </div>
      <div class="menu-row">
        <span class="row-label">翻牌动画</span>
        <el-switch v-model="enableAnimations" />
      </div>
      <div v-if="prefersReducedMotion" class="menu-tip">
        系统已请求减少动效，动画将自动简化
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { useUserPreferences } from '@/hooks/useUserPreferences';

const { enableBackground, enableAnimations, prefersReducedMotion } = useUserPreferences();
</script>

<style scoped>
.settings-trigger {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease, transform 0.2s ease;
  color: var(--text-primary);
}
.settings-trigger:hover {
  transform: rotate(45deg);
}
.gear-icon {
  font-size: 18px;
  line-height: 1;
}

.settings-menu {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.menu-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.menu-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.row-label {
  font-size: 13px;
  color: var(--text-primary);
}

.menu-tip {
  font-size: 11px;
  color: var(--text-secondary);
  padding-top: 4px;
  border-top: 1px dashed var(--border-color);
}
</style>
