<template>
  <div v-if="showStatus" class="witch-potion-status">
    <el-divider />
    <el-card shadow="never" class="potion-status-card">
      <template #header>
        <span class="status-header">🧙‍♀️ 你的用药情况</span>
      </template>
      <div class="potion-list">
        <div class="potion-item">
          <span class="potion-label">解药：</span>
          <el-tag v-if="antidoteUsed" type="success" size="small">已使用</el-tag>
          <el-tag v-else type="info" size="small">未使用</el-tag>
          <span v-if="saveTarget" class="potion-target">→ {{ saveTarget }}</span>
        </div>
        <div class="potion-item">
          <span class="potion-label">毒药：</span>
          <el-tag v-if="poisonUsed" type="danger" size="small">已使用</el-tag>
          <el-tag v-else type="info" size="small">未使用</el-tag>
          <span v-if="poisonTarget" class="potion-target">→ {{ poisonTarget }}</span>
        </div>
      </div>
      <p class="potion-hint">💡 解药和毒药各只能使用一次</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  antidoteUsed: boolean;
  poisonUsed: boolean;
  saveTarget?: string | null;
  poisonTarget?: string | null;
}>();

const showStatus = computed(() => props.antidoteUsed || props.poisonUsed);
</script>

<style scoped>
.witch-potion-status {
  margin-top: 12px;
}

.potion-status-card {
  background: var(--bg-card-glass, rgba(255, 255, 255, 0.8));
}

.status-header {
  font-weight: bold;
  font-size: 14px;
}

.potion-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.potion-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.potion-label {
  font-size: 13px;
  color: var(--text-primary);
  min-width: 48px;
}

.potion-target {
  font-size: 12px;
  color: var(--text-secondary);
}

.potion-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
}
</style>
