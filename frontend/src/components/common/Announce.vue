<template>
  <el-card shadow="never">
    <template #header>系统公告</template>
    <div class="announce-scroll">
      <el-timeline>
        <el-timeline-item v-for="item in announcements" :key="item.id" :timestamp="item.time">
          {{ item.content }}
        </el-timeline-item>
      </el-timeline>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  announcements: Array<{ id: string; content: string; time: string }>;
}>();
</script>

<style scoped>
.announce-scroll {
  max-height: 240px;
  overflow-y: auto;
  padding-right: 4px;
}
</style>
