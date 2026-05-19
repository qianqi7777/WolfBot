<template>
  <div class="page-shell">
    <el-space direction="vertical" fill style="width: 100%">
      <el-card>
        <template #header>结算结果</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="房间号">{{ gameId }}</el-descriptions-item>
          <el-descriptions-item label="胜利阵营">{{ result?.winnerFaction ?? store.winnerFaction ?? 'pending' }}</el-descriptions-item>
          <el-descriptions-item label="当前轮次">{{ result?.currentRound ?? store.currentRound }}</el-descriptions-item>
          <el-descriptions-item label="对局状态">{{ store.gameStatus }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <player-list :players="result?.players ?? store.players" />

      <el-card>
        <template #header>复盘摘要</template>
        <el-timeline>
          <el-timeline-item
            v-for="(item, index) in result?.announcements ?? store.announceList.map((entry) => entry.content)"
            :key="`${index}-${item}`"
          >
            {{ item }}
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <el-button @click="goHome">返回首页</el-button>
    </el-space>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { getResult } from '@/api/gameApi';
import PlayerList from '@/components/game/PlayerList.vue';
import { useGameStore } from '@/store/modules/gameStore';
import type { GameResultPayload } from '@/types/game';

const props = defineProps<{ gameId: string }>();
const router = useRouter();
const store = useGameStore();
const result = ref<GameResultPayload | null>(null);

const loadResult = async () => {
  result.value = await getResult(props.gameId);
  store.setResult(result.value);
};

const goHome = async () => {
  await router.push({ name: 'home' });
};

onMounted(loadResult);
</script>
