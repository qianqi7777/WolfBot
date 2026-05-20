<template>
  <el-card shadow="never">
    <template #header>系统公告</template>
    <div ref="scrollRef" class="announce-scroll">
      <el-timeline>
        <el-timeline-item v-for="item in announcements" :key="item.id" :timestamp="item.time">
          {{ item.content }}
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue';

const props = defineProps<{
  announcements: Array<{ id: string; content: string; time: string }>;
}>();

const scrollRef = ref<HTMLElement | null>(null);

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
.announce-scroll {
  max-height: 240px;
  overflow-y: auto;
  padding-right: 4px;
  scroll-behavior: smooth;
}
</style>
