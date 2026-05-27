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

      <!-- 全场亮牌仪式：所有玩家的牌从背面依次翻开 -->
      <el-card v-if="revealPlayers.length > 0">
        <template #header>全场亮牌</template>
        <div class="reveal-grid">
          <div
            v-for="p in revealPlayers"
            :key="p.id"
            class="reveal-card"
            :class="{ flipped: flippedSet.has(p.id), 'no-motion': !animationsEffective }"
          >
            <div class="reveal-card-inner">
              <!-- 牌背 -->
              <div class="reveal-card-face reveal-card-back">
                <img v-if="cardBackUrl" :src="cardBackUrl" alt="牌背" />
                <div v-else class="css-card-back-mini">
                  <div class="logo-mark-mini">狼</div>
                </div>
              </div>
              <!-- 牌正面 -->
              <div class="reveal-card-face reveal-card-front">
                <RoleCardBig :role="(p.role as RoleType)" :highlight="isWinnerSide(p)" />
              </div>
            </div>
            <div class="reveal-card-name">{{ p.seatNumber }}号({{ p.name }})</div>
          </div>
        </div>
      </el-card>

      <!-- MVP / SVP 展示 -->
      <el-card v-if="result?.mvp || result?.svp">
        <template #header>本局最佳</template>
        <div class="mvp-row">
          <div v-if="result?.mvp" class="mvp-card mvp-winner">
            <div class="mvp-badge">MVP</div>
            <div class="mvp-name">{{ result.mvp.playerName }}</div>
            <el-tag :type="roleTagType(result.mvp.role as RoleType)" effect="dark" size="small">
              {{ roleLabels[result.mvp.role as RoleType] ?? result.mvp.role }}
            </el-tag>
            <div class="mvp-score">{{ result.mvp.score }} 分</div>
          </div>
          <div v-if="result?.svp" class="mvp-card mvp-loser">
            <div class="mvp-badge svp">SVP</div>
            <div class="mvp-name">{{ result.svp.playerName }}</div>
            <el-tag :type="roleTagType(result.svp.role as RoleType)" effect="dark" size="small">
              {{ roleLabels[result.svp.role as RoleType] ?? result.svp.role }}
            </el-tag>
            <div class="mvp-score">{{ result.svp.score }} 分</div>
          </div>
        </div>
      </el-card>

      <!-- 身份揭示 -->
      <el-card>
        <template #header>身份揭示</template>
        <el-table :data="revealPlayers" stripe border style="width: 100%">
          <el-table-column label="玩家" width="120" align="center">
            <template #default="{ row }">
              <strong>{{ row.seatNumber }}号({{ row.name }})</strong>
            </template>
          </el-table-column>
          <el-table-column label="身份" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="roleTagType(row.role as RoleType)" effect="dark">
                {{ roleLabels[row.role as RoleType] ?? '未知' }}
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

      <!-- 贡献率排名 -->
      <el-card v-if="result?.contributions && result.contributions.length > 0">
        <template #header>贡献率排名</template>
        <el-table :data="result.contributions" stripe border style="width: 100%">
          <el-table-column label="排名" width="60" align="center">
            <template #default="{ $index }">
              <span :class="{ 'rank-gold': $index === 0, 'rank-silver': $index === 1 }">
                {{ $index + 1 }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="玩家" min-width="120" align="center">
            <template #default="{ row }">
              {{ row.playerName }}
            </template>
          </el-table-column>
          <el-table-column label="身份" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="roleTagType(row.role as RoleType)" size="small">
                {{ roleLabels[row.role as RoleType] ?? row.role }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="得分" width="80" align="center">
            <template #default="{ row }">
              <span :style="{ color: row.score >= 0 ? '#67C23A' : '#F56C6C' }">
                {{ row.score > 0 ? '+' : '' }}{{ row.score }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="得分明细" min-width="200">
            <template #default="{ row }">
              <span v-for="(d, i) in row.details" :key="i" class="detail-tag">
                <el-tag size="small" :type="d.includes('+') ? 'success' : d.includes('-') ? 'danger' : 'info'">
                  {{ d }}
                </el-tag>
              </span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 每轮事件时间线 -->
      <el-card v-if="roundTimeline.length > 0">
        <template #header>对局时间线</template>
        <el-timeline>
          <el-timeline-item
            v-for="(item, index) in roundTimeline"
            :key="index"
            :type="item.type === 'night' ? 'primary' : 'warning'"
            :timestamp="item.label"
            placement="top"
          >
            <div v-for="(line, li) in item.lines" :key="li" class="timeline-line">{{ line }}</div>
          </el-timeline-item>
        </el-timeline>
      </el-card>

      <!-- 复盘摘要 -->
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
import RoleCardBig from '@/components/common/RoleCardBig.vue';
import { useUserPreferences } from '@/hooks/useUserPreferences';
import { useGameStore } from '@/store/modules/gameStore';
import type { GameResultPayload, Player, RoleType, RoundEvent } from '@/types/game';
import { ROLE_LABELS, ROLE_FACTION } from '@/utils/constants';
import { getCardBack } from '@/utils/cardImage';

const WOLF_FACTION_ROLES: RoleType[] = ['wolf'];
const GOD_ROLES: RoleType[] = ['prophet', 'guard', 'hunter', 'witch'];

const props = defineProps<{ gameId: string }>();
const router = useRouter();
const store = useGameStore();
const result = ref<GameResultPayload | null>(null);
const roleLabels = ROLE_LABELS;
const cardBackUrl = computed(() => getCardBack());
const { animationsEffective } = useUserPreferences();

const flippedSet = ref<Set<string>>(new Set());

const loadResult = async () => {
  result.value = await getResult(props.gameId);
  store.setResult(result.value);
  // 全场亮牌仪式：依次延迟翻开
  flippedSet.value = new Set();
  const list = revealPlayers.value;
  const stepMs = animationsEffective.value ? 300 : 0;
  list.forEach((p, idx) => {
    setTimeout(() => {
      flippedSet.value = new Set([...flippedSet.value, p.id]);
    }, 300 + idx * stepMs);
  });
};

/** 当前玩家是否属于胜方（高亮用） */
function isWinnerSide(p: Player): boolean {
  const faction = result.value?.winnerFaction ?? store.winnerFaction;
  if (!faction) return false;
  return ROLE_FACTION[p.role] === faction;
}

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

/** 构建对局时间线 */
const roundTimeline = computed(() => {
  const events = result.value?.roundEvents ?? [];
  const players = result.value?.players ?? [];
  const playerMap = new Map(players.map(p => [p.id, p]));

  const getName = (id: string | null | undefined) => {
    if (!id) return '未知';
    const p = playerMap.get(id);
    return p ? `${p.seatNumber}号(${p.name})` : '未知';
  };

  const timeline: Array<{ type: string; label: string; lines: string[] }> = [];

  for (const event of events) {
    if (event.type === 'night') {
      const lines: string[] = [];
      if (event.killed_player_id) {
        lines.push(`💀 ${getName(event.killed_player_id)} 被杀害`);
      } else if (event.guard_blocked) {
        lines.push('🛡️ 平安夜（守卫成功守住）');
      } else {
        lines.push('🌙 平安夜');
      }
      // 预言家验人
      if (event.prophet_checks) {
        for (const check of event.prophet_checks) {
          const result = check.is_wolf ? '🐺 狼人' : '👤 好人';
          lines.push(`🔮 预言家查验 ${getName(check.target_id)} → ${result}`);
        }
      }
      // 守卫守护
      if (event.guard_saves) {
        for (const save of event.guard_saves) {
          if (save.saved) {
            lines.push(`🛡️ 守卫守住 ${getName(save.target_id)}`);
          }
        }
      }
      timeline.push({
        type: 'night',
        label: `第${event.round}轮 · 夜晚`,
        lines,
      });
    } else if (event.type === 'vote') {
      const lines: string[] = [];
      // 投票明细
      if (event.votes) {
        for (const vote of event.votes) {
          const voter = getName(vote.voterId);
          if (vote.targetId === 'abstain') {
            lines.push(`🗳️ ${voter} 弃票`);
          } else {
            lines.push(`🗳️ ${voter} → ${getName(vote.targetId)}`);
          }
        }
      }
      if (event.eliminated_id) {
        lines.push(`⛔ ${getName(event.eliminated_id)} 被放逐`);
      } else {
        lines.push('⚖️ 无人出局');
      }
      timeline.push({
        type: 'vote',
        label: `第${event.round}轮 · 投票`,
        lines,
      });
    }
  }

  return timeline;
});

const goHome = () => {
  store.resetGame();
  router.push({ name: 'home' });
};

onMounted(loadResult);
</script>

<style scoped>
.mvp-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.mvp-card {
  flex: 1;
  min-width: 200px;
  padding: 16px;
  border-radius: 12px;
  text-align: center;
  border: 2px solid;
}

.mvp-winner {
  border-color: #E6A23C;
  background: linear-gradient(135deg, #FDF6EC 0%, #FFF 100%);
}

.mvp-loser {
  border-color: #909399;
  background: linear-gradient(135deg, #F4F4F5 0%, #FFF 100%);
}

.mvp-badge {
  font-size: 20px;
  font-weight: 900;
  color: #E6A23C;
  margin-bottom: 8px;
}

.mvp-badge.svp {
  color: #909399;
}

.mvp-name {
  font-size: 16px;
  font-weight: bold;
  margin: 4px 0;
}

.mvp-score {
  font-size: 20px;
  font-weight: bold;
  margin-top: 8px;
  color: #67C23A;
}

.rank-gold {
  color: #E6A23C;
  font-weight: bold;
}

.rank-silver {
  color: #909399;
  font-weight: bold;
}

.detail-tag {
  margin: 2px;
  display: inline-block;
}

.timeline-line {
  line-height: 1.8;
  font-size: 14px;
}

/* 全场亮牌仪式 */
.reveal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
  padding: 8px 0;
}

.reveal-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.reveal-card-inner {
  position: relative;
  width: 100%;
  aspect-ratio: 2 / 3;
  transition: transform 0.7s cubic-bezier(0.4, 0, 0.2, 1);
  transform-style: preserve-3d;
  -webkit-transform-style: preserve-3d;
}

.reveal-card.flipped .reveal-card-inner {
  transform: rotateY(180deg);
}

.reveal-card.no-motion .reveal-card-inner {
  transition: none;
}

.reveal-card-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  border-radius: 8px;
  overflow: hidden;
}

.reveal-card-back {
  z-index: 2;
}

.reveal-card-front {
  transform: rotateY(180deg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.reveal-card-back img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.css-card-back-mini {
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #1f2937, #0f172a);
  border: 2px solid #4b5563;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-mark-mini {
  font-size: 32px;
  font-weight: 800;
  color: #fbbf24;
  letter-spacing: 0.05em;
}

.reveal-card-name {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}
</style>
