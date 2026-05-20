<template>
  <div v-if="remainingSeconds !== null" class="countdown-timer" :class="timerClass">
    <div class="timer-bar">
      <div class="timer-fill" :style="{ width: percentage + '%' }" />
    </div>
    <span class="timer-text">{{ Math.max(0, remainingSeconds) }}s</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = defineProps<{
  deadline: string | null;  // ISO 8601 UTC
  totalSeconds?: number;    // 用于计算进度条宽度
}>();

const now = ref(Date.now());
let timer: ReturnType<typeof setInterval> | null = null;

onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now();
  }, 250);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});

const remainingSeconds = computed(() => {
  if (!props.deadline) return null;
  const deadlineMs = new Date(props.deadline).getTime();
  const remaining = Math.floor((deadlineMs - now.value) / 1000);
  return remaining > 0 ? remaining : 0;
});

const percentage = computed(() => {
  if (!props.totalSeconds || remainingSeconds.value === null) return 100;
  const remaining = remainingSeconds.value;
  return Math.min(100, (remaining / props.totalSeconds) * 100);
});

const timerClass = computed(() => {
  const remaining = remainingSeconds.value ?? 0;
  if (remaining <= 5) return 'timer-critical';
  if (remaining <= 10) return 'timer-warning';
  return 'timer-normal';
});
</script>

<style scoped>
.countdown-timer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.timer-bar {
  flex: 1;
  height: 8px;
  background: #ebeef5;
  border-radius: 4px;
  overflow: hidden;
}
.timer-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.25s linear;
}
.timer-normal .timer-fill { background: #409eff; }
.timer-warning .timer-fill { background: #e6a23c; }
.timer-critical .timer-fill { background: #f56c6c; }
.timer-text {
  font-size: 14px;
  font-weight: bold;
  min-width: 32px;
  text-align: right;
}
.timer-warning .timer-text { color: #e6a23c; }
.timer-critical .timer-text { color: #f56c6c; }
</style>
