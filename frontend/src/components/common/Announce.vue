<template>
  <div class="announce-panel">
    <div ref="scrollRef" class="announce-scroll">
      <div v-if="!announcements.length" class="announce-empty">暂无公告</div>
      <div v-for="item in announcements" :key="item.id" class="announce-item">
        <span class="announce-time">{{ formatTime(item.time) }}</span>
        <span class="announce-content">{{ item.content }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

const props = defineProps<{
  announcements: Array<{ id: string; content: string; time: string }>;
}>();

const scrollRef = ref<HTMLElement | null>(null);

/** 格式化时间 */
const formatTime = (isoTime: string): string => {
  try {
    const d = new Date(isoTime);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  } catch {
    return '';
  }
};

/** 滚动到底部 */
const scrollToBottom = () => {
  nextTick(() => {
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight;
    }
  });
};

// 公告数量变化时自动滚动到最新
watch(() => props.announcements.length, () => {
  scrollToBottom();
});
</script>

<style scoped>
.announce-panel {
  background: var(--bg-card-glass);
  border-radius: 6px;
  padding: 8px;
  max-height: 120px;
  overflow-y: auto;
}
.announce-scroll {
  scroll-behavior: smooth;
}
.announce-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 8px 0;
}
.announce-item {
  display: flex;
  gap: 6px;
  padding: 3px 0;
  font-size: 12px;
  line-height: 1.4;
}
.announce-time {
  color: var(--text-secondary);
  flex-shrink: 0;
  font-size: 11px;
}
.announce-content {
  color: var(--text-primary);
}
</style>
