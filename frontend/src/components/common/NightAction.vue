<template>
  <div class="night-action">
    <el-card shadow="never" class="night-panel" :class="{ 'is-active': !disabled }">
      <template #header>
        <div class="panel-header">🌙 夜间行动</div>
      </template>

      <!-- 狼人：选择击杀目标 -->
      <template v-if="role === 'wolf'">
        <el-alert
          v-if="!disabled"
          title="请在上方圆桌点击要袭击的玩家"
          type="error"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
        <p v-if="teammateSeats && teammateSeats.length" class="teammate-hint">你的狼人队友：{{ teammateSeats.join('号、') }}号</p>
        <!-- 狼人队友的实时选择 -->
        <div v-if="wolfTargetUpdates && wolfTargetUpdates.length" class="wolf-target-updates">
          <div v-for="update in wolfTargetUpdates" :key="update.wolfId" class="wolf-target-item">
            <el-tag type="warning" size="small">{{ update.wolfSeat }}号</el-tag>
            <span class="wolf-target-arrow">→</span>
            <el-tag type="danger" size="small">{{ update.targetSeat }}号</el-tag>
          </div>
        </div>
      </template>

      <!-- 预言家：选择查验目标 -->
      <template v-else-if="role === 'prophet'">
        <el-alert
          v-if="!disabled"
          title="请在上方圆桌点击要查验身份的玩家"
          type="info"
          :closable="false"
          show-icon
        />
        <!-- 查验结果显示 -->
        <div v-if="checkResult" class="check-result" style="margin-top: 12px">
          <el-alert
            :title="`${checkResult.seatLabel} 的身份是：${roleLabels[checkResult.role]}`"
            :type="checkResult.role === 'wolf' ? 'error' : 'success'"
            show-icon
          />
        </div>
      </template>

      <!-- 守卫：选择守护目标 -->
      <template v-else-if="role === 'guard'">
        <el-alert
          v-if="!disabled"
          title="请在上方圆桌点击要守护的玩家（可点自己）"
          type="success"
          :closable="false"
          show-icon
        />
        <div v-if="guardResult" class="check-result" style="margin-top: 12px">
          <el-alert
            :title="guardResult.guardBlocked ? `你守住了 ${guardResult.seatLabel}` : `你守护了 ${guardResult.seatLabel}`"
            type="success"
            show-icon
          />
        </div>
      </template>

      <!-- 女巫：看到刀口，选择是否救 + 选毒杀目标 -->
      <template v-else-if="role === 'witch'">
        <!-- 解药：显示刀口，选择救/不救 -->
        <div v-if="!antidoteUsed && !saveSubmitted" class="witch-save-section">
          <el-alert
            :title="wolfKillInfo"
            type="warning"
            show-icon
            :closable="false"
            style="margin-bottom: 12px"
          />
          <p>是否使用解药？</p>
          <div class="potion-select" style="margin-top: 8px">
            <el-button type="success" :disabled="disabled" @click="handleSaveSubmit(true)">
              💚 使用解药救活
            </el-button>
            <el-button type="info" :disabled="disabled" @click="handleSaveSubmit(false)">
              ⏭️ 不使用解药
            </el-button>
          </div>
        </div>
        <div v-else-if="antidoteUsed || saveSubmitted" class="witch-save-section">
          <el-alert title="解药已使用或跳过" type="info" show-icon :closable="false" class="used-alert" />
        </div>
        <!-- 毒药：选择毒杀目标 -->
        <div v-if="!poisonUsed && !poisonSubmitted" class="witch-poison-section">
          <el-divider />
          <el-alert
            v-if="!disabled"
            title="如果要使用毒药，请在上方圆桌点击目标玩家"
            type="error"
            :closable="false"
            show-icon
          />
        </div>
        <div v-else-if="poisonUsed || poisonSubmitted" class="witch-poison-section">
          <el-divider />
          <el-alert title="毒药已使用或跳过" type="info" show-icon :closable="false" class="used-alert" />
        </div>
        <!-- 结束回合按钮 (如果没有用毒，可以选择结束) -->
        <div v-if="!poisonUsed && !poisonSubmitted && (!(!antidoteUsed && !saveSubmitted))" style="margin-top: 12px">
            <el-button type="info" plain :disabled="disabled" style="width: 100%" @click="handleSkipPoison">
              结束回合 (不使用毒药)
            </el-button>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { Player, RoleType } from '@/types/game';

const props = defineProps<{
  role: RoleType;
  players: Player[];
  currentPlayerId: string;
  nightResult?: Record<string, any> | null;
  prophetCheckResult?: { seatLabel: string; role: RoleType } | null;
  disabled?: boolean;
  teammateSeats?: number[];
  wolfTargetUpdates?: { wolfId: string; wolfSeat: number; targetSeat: number }[];
  antidoteUsed?: boolean;
  poisonUsed?: boolean;
  wolfKillTargetId?: string | null;
  wolfKillTargetLabel?: string;
}>();

const emit = defineEmits<{
  submit: [targetId: string, actionType?: string];
}>();

// 本地状态
const saveSubmitted = ref(false);
const poisonSubmitted = ref(false);

const handleSaveSubmit = (useSave: boolean) => {
  if (props.disabled) return;
  if (useSave) {
    emit('submit', props.wolfKillTargetId || '', 'save');
  } else {
    emit('submit', 'skip', 'skip_save');
  }
  saveSubmitted.value = true;
};

const handleSkipPoison = () => {
    if (props.disabled) return;
    emit('submit', 'skip', 'skip_poison');
    poisonSubmitted.value = true;
};

// 角色文案映射
const roleLabels: Record<string, string> = {
  wolf: '🐺 狼人',
  civilian: '🧑‍🌾 平民',
  prophet: '🔮 预言家',
  witch: '🧙‍♀️ 女巫',
  guard: '🛡️ 守卫',
  hunter: '🔫 猎人',
};

// 结果回显逻辑
const checkResult = computed(() => {
  if (props.role !== 'prophet' || !props.prophetCheckResult) return null;
  return props.prophetCheckResult;
});

const guardResult = computed(() => {
  if (props.role !== 'guard' || !props.nightResult) return null;
  const guardedTargetId = typeof props.nightResult.guardedPlayerId === 'string'
    ? props.nightResult.guardedPlayerId
    : null;
  if (!guardedTargetId) return null;
  const target = props.players.find((p) => p.id === guardedTargetId);
  if (!target) return null;
  return {
    seatLabel: `${target.seatNumber}号(${target.name})`,
    guardBlocked: !!props.nightResult.guardBlocked,
  };
});

const wolfKillInfo = computed(() => {
  if (props.antidoteUsed || saveSubmitted.value) {
    return '';
  }
  if (props.wolfKillTargetId === null) {
    return '等待狼人选择目标...';
  }
  if (props.wolfKillTargetId === 'none') {
    return '平安夜，昨晚没有玩家被击杀。';
  }
  if (props.wolfKillTargetLabel) {
    return `昨晚 ${props.wolfKillTargetLabel} 被击杀。`;
  }
  return '获取刀口信息中...';
});
const wolfKillLabel = computed(() => {
  if (props.wolfKillTargetId === 'none') return '';
  return props.wolfKillTargetLabel || '';
});
</script>

<style scoped>
.night-action {
  transition: all 0.5s ease;
}
.night-panel {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}
.night-panel.is-active {
  border-color: var(--accent-color);
  box-shadow: 0 0 10px rgba(var(--accent-color-rgb), 0.2);
}
.panel-header {
  font-weight: bold;
  color: var(--text-primary);
}
.teammate-hint {
  color: var(--faction-wolf, #ef4444);
  font-size: 14px;
  margin-bottom: 8px;
}
.wolf-target-updates {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.wolf-target-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-primary);
  padding: 4px 8px;
  border-radius: 4px;
}
.wolf-target-arrow {
  color: var(--text-secondary);
}
.witch-save-section,
.witch-poison-section {
  display: flex;
  flex-direction: column;
}
.potion-select {
  display: flex;
  gap: 12px;
}
.used-alert {
  opacity: 0.7;
}
</style>
