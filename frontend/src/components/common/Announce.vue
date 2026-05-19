<template>
  <el-card shadow="never">
    <template #header>系统公告</template>
    <el-timeline>
      <el-timeline-item v-for="item in announcements" :key="item.id" :timestamp="item.time">
        {{ item.content }}
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  announcements: Array<{ id: string; content: string; time: string }>;
}>();
</script>
