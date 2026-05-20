<template>
  <div class="page-shell">
    <el-space direction="vertical" fill style="width: 100%">
      <el-card>
        <template #header>结算结果</template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="房间号">{{ gameId }}</el-descriptions-item>
          <el-descriptions-item label="胜利阵营">
            <el-tag :type="winnerTagType" size="large">
              {{ winnerLabel }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="总轮次">{{ result?.currentRound ?? store.currentRound }}</el-descriptions-item>
          <el-descriptions-item label="对局状态">已结束</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 身份揭示：结算页专门展示所有玩家身份 -->
      <el-card>
        <template #header>身份揭示</template>
        <el-table :data="revealPlayers" stripe border style="width: 100%">
          <el-table-column label="座位" width="80" align="center">
            <template #default="{ row }">
              <strong>{{ row.seatNumber }}号</strong>
            </template>
          </el-table-column>
          <el-table-column label="身份" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="roleTagType(row.role)" effect="dark">
                {{ roleLabels[row.role] ?? '未知' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="阵营" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="factionTagType(row.role)" size="small">
                {{ factionLabel(row.role) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.isAlive ? 'success' : 'danger'" size="small">
                {{ row.isAlive ? '存活' : '淘汰' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80" align="center">
            <template #default="{ row }">
              {{ row.isAI ? 'AI' : '真人' }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>

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

      <el-button type="primary" size="large" @click="goHome">返回首页</el-button>
    </el-space>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { getResult } from '@/api/gameApi';
import { useGameStore } from '@/store/modules/gameStore';
import type { GameResultPayload, RoleType } from '@/types/game';
import { ROLE_LABELS } from '@/utils/constants';

const WOLF_FACTION_ROLES: RoleType[] = ['wolf'];
const GOD_ROLES: RoleType[] = ['prophet', 'guard', 'hunter', 'witch'];

const props = defineProps<{ gameId: string }>();
const router = useRouter();
const store = useGameStore();
const result = ref<GameResultPayload | null>(null);
const roleLabels = ROLE_LABELS;

const loadResult = async () => {
  result.value = await getResult(props.gameId);
  store.setResult(result.value);
};

/** 结算页玩家列表（按座位号排序） */
const revealPlayers = computed(() => {
  const players = result.value?.players ?? store.players;
  return [...players].sort((a, b) => a.seatNumber - b.seatNumber);
});

const winnerLabel = computed(() => {
  const faction = result.value?.winnerFaction ?? store.winnerFaction;
  if (faction === 'civilian') return '好人阵营';
  if (faction === 'wolf') return '狼人阵营';
  return faction ?? 'pending';
});

const winnerTagType = computed(() => {
  const faction = result.value?.winnerFaction ?? store.winnerFaction;
  if (faction === 'civilian') return 'success';
  if (faction === 'wolf') return 'danger';
  return 'info';
});

const factionLabel = (role: RoleType) => {
  if (WOLF_FACTION_ROLES.includes(role)) return '狼人';
  if (GOD_ROLES.includes(role)) return '神职';
  if (role === 'civilian') return '平民';
  return '未知';
};

const roleTagType = (role: RoleType) => {
  if (role === 'wolf') return 'danger';
  if (role === 'prophet') return '';
  if (role === 'guard') return 'success';
  if (role === 'hunter') return 'warning';
  if (role === 'witch') return 'warning';
  if (role === 'civilian') return 'info';
  return 'info';
};

const factionTagType = (role: RoleType) => {
  if (WOLF_FACTION_ROLES.includes(role)) return 'danger';
  if (GOD_ROLES.includes(role)) return 'warning';
  return 'info';
};

const goHome = () => {
  store.resetGame();
  router.push({ name: 'home' });
};

onMounted(loadResult);
</script>
