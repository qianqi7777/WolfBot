<template>
  <div class="night-action">
    <el-card header="夜间行动">
      <!-- 狼人：选择击杀目标 -->
      <template v-if="role === 'wolf'">
        <p>请选择要击杀的目标：</p>
        <p v-if="teammates.length" class="teammate-hint">你的狼人队友：{{ teammates.join('、') }}</p>
        <!-- 狼人队友的实时选择 -->
        <div v-if="wolfTargetUpdates.length" class="wolf-target-updates">
          <div v-for="update in wolfTargetUpdates" :key="update.wolfId" class="wolf-target-item">
            <el-tag type="warning" size="small">{{ update.wolfSeat }}号</el-tag>
            <span class="wolf-target-arrow">→</span>
            <el-tag type="danger" size="small">{{ update.targetSeat }}号</el-tag>
          </div>
        </div>
        <el-radio-group v-model="selectedTarget" :disabled="disabled">
          <el-radio
            v-for="player in targetPlayers"
            :key="player.id"
            :value="player.id"
          >
            {{ player.seatNumber }}号({{ player.name }})
          </el-radio>
        </el-radio-group>
        <el-button
          type="danger"
          :disabled="disabled || !selectedTarget"
          style="margin-top: 12px"
          @click="handleSubmit"
        >
          确认击杀
        </el-button>
      </template>

      <!-- 预言家：选择查验目标 -->
      <template v-else-if="role === 'prophet'">
        <p>请选择要查验的玩家：</p>
        <el-radio-group v-model="selectedTarget" :disabled="disabled">
          <el-radio
            v-for="player in targetPlayers"
            :key="player.id"
            :value="player.id"
          >
            {{ player.seatNumber }}号({{ player.name }})
          </el-radio>
        </el-radio-group>
        <el-button
          type="primary"
          :disabled="disabled || !selectedTarget"
          style="margin-top: 12px"
          @click="handleSubmit"
        >
          确认查验
        </el-button>
        <!-- 查验结果显示 -->
        <div v-if="checkResult" class="check-result">
          <el-alert
            :title="`${checkResult.seatLabel} 的身份是：${roleLabels[checkResult.role]}`"
            :type="checkResult.role === 'wolf' ? 'error' : 'success'"
            show-icon
          />
        </div>
      </template>

      <!-- 守卫：选择守护目标 -->
      <template v-else-if="role === 'guard'">
        <p>请选择要守护的玩家：</p>
        <el-radio-group v-model="selectedTarget" :disabled="disabled">
          <el-radio
            v-for="player in targetPlayers"
            :key="player.id"
            :value="player.id"
          >
            {{ player.seatNumber }}号({{ player.name }})
          </el-radio>
        </el-radio-group>
        <el-button
          type="success"
          :disabled="disabled || !selectedTarget"
          style="margin-top: 12px"
          @click="handleSubmit"
        >
          确认守护
        </el-button>
        <div v-if="guardResult" class="check-result">
          <el-alert
            :title="guardResult.guardBlocked ? `你守住了 ${guardResult.seatLabel}` : `你守护了 ${guardResult.seatLabel}`"
            type="success"
            show-icon
          />
        </div>
      </template>

      <!-- 女巫：选择药剂类型和目标 -->
      <template v-else-if="role === 'witch'">
        <p>请选择使用的药剂：</p>
        <div class="potion-select">
          <el-radio-group v-model="potionType" :disabled="disabled" size="large">
            <el-radio-button
              value="save"
              :disabled="antidoteUsed"
            >
              💚 解药（救人）
              <span v-if="antidoteUsed" class="used-label">已使用</span>
            </el-radio-button>
            <el-radio-button
              value="poison"
              :disabled="poisonUsed"
            >
              💀 毒药（杀人）
              <span v-if="poisonUsed" class="used-label">已使用</span>
            </el-radio-button>
          </el-radio-group>
        </div>
        <p v-if="potionType === 'save'" class="hint-text">选择要解救的玩家（如果该玩家被狼人袭击，将存活）</p>
        <p v-if="potionType === 'poison'" class="hint-text">选择要毒杀的玩家（该玩家将在天亮时死亡）</p>
        <el-radio-group v-model="selectedTarget" :disabled="disabled || !potionType">
          <el-radio
            v-for="player in targetPlayers"
            :key="player.id"
            :value="player.id"
          >
            {{ player.seatNumber }}号({{ player.name }})
          </el-radio>
        </el-radio-group>
        <el-button
          type="warning"
          :disabled="disabled || !selectedTarget || !potionType"
          style="margin-top: 12px"
          @click="handleSubmit"
        >
          确认使用{{ potionType === 'save' ? '解药' : '毒药' }}
        </el-button>
      </template>

      <!-- 无夜间行动的角色（平民、猎人、白痴等）：等待 -->
      <template v-else>
        <p>夜间等待中...</p>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import type { Player, RoleType, WolfTargetUpdate } from '@/types/game';
import { ROLE_LABELS } from '@/utils/constants';

const props = defineProps<{
  role: RoleType;
  players: Player[];
  disabled?: boolean;
  currentPlayerId?: string;
  nightResult?: {
    guardedPlayerId?: string | null;
    guardBlocked?: boolean;
  } | null;
  teammateSeats?: string[];
  wolfTargetUpdates?: WolfTargetUpdate[];
  antidoteUsed?: boolean;
  poisonUsed?: boolean;
}>();

const emit = defineEmits<{
  submit: [targetId: string, actionType?: string];
}>();

const selectedTarget = ref('');
const potionType = ref('');  // 'save' | 'poison'
const roleLabels = ROLE_LABELS;

/** 狼人队友（从后端推送的 teammates 数据） */
const teammates = computed(() => props.teammateSeats ?? []);

/** 狼人队友的实时刀目标 */
const wolfTargetUpdates = computed(() => props.wolfTargetUpdates ?? []);

/** 女巫解药已使用 */
const antidoteUsed = computed(() => props.antidoteUsed ?? false);

/** 女巫毒药已使用 */
const poisonUsed = computed(() => props.poisonUsed ?? false);

/** 目标玩家：仅存活的玩家，狼人和女巫毒药可以选自己 */
const targetPlayers = computed(() => {
  const canTargetSelf = props.role === 'wolf';
  return props.players.filter(
    (p) => p.isAlive && (canTargetSelf || p.id !== props.currentPlayerId),
  );
});

/** 查验结果显示（暂从 announce 获取，Phase 2 重构） */
const checkResult = computed(() => {
  // TODO: Phase 2 从私发 announce 解析查验结果
  return null;
});

const guardResult = computed(() => {
  if (props.role !== 'guard' || !props.nightResult?.guardedPlayerId) return null;
  const target = props.players.find((p) => p.id === props.nightResult!.guardedPlayerId);
  return target ? { seatLabel: `${target.seatNumber}号`, guardBlocked: props.nightResult.guardBlocked ?? false } : null;
});

const handleSubmit = () => {
  if (selectedTarget.value) {
    emit('submit', selectedTarget.value, potionType.value || undefined);
    selectedTarget.value = '';
    potionType.value = '';
  }
};
</script>

<style scoped>
.night-action {
  margin-bottom: 16px;
}
.teammate-hint {
  color: #e6a23c;
  margin-bottom: 8px;
  font-weight: bold;
}
.check-result {
  margin-top: 12px;
}
.wolf-target-updates {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  padding: 8px;
  background: #fdf6ec;
  border-radius: 4px;
  border: 1px solid #faecd8;
}
.wolf-target-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.wolf-target-arrow {
  color: #e6a23c;
  font-weight: bold;
}
.potion-select {
  margin-bottom: 16px;
}
.potion-select .el-radio-button {
  margin-right: 8px;
}
.hint-text {
  color: #909399;
  font-size: 13px;
  margin: 8px 0;
}
.used-label {
  color: #c0c4cc;
  font-size: 12px;
}
</style>
