<template>
  <div class="page-shell">
    <el-card>
      <template #header>房间 {{ gameId }}</template>
      <p>等待更多玩家加入并准备开局。</p>
      <el-button type="primary" @click="goGame">进入对局页</el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const props = defineProps<{ gameId: string }>();
const router = useRouter();

const goGame = async () => {
  await router.push({ name: 'game', params: { gameId: props.gameId } });
};
</script>
