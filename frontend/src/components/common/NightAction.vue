<template>
  <div class="night-action">
    <el-card header="夜间行动">
      <!-- 狼人：选择击杀目标 -->
      <template v-if="role === 'wolf'">
        <p>请选择要击杀的目标：</p>
        <el-radio-group v-model="selectedTarget" :disabled="disabled">
          <el-radio
            v-for="player in targetPlayers"
            :key="player.id"
            :value="player.id"
          >
            {{ player.name }}{{ player.isAI ? '（AI）' : '' }}
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
            {{ player.name }}{{ player.isAI ? '（AI）' : '' }}
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
            :title="`${checkResult.playerName} 的身份是：${roleLabels[checkResult.role]}`"
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
            {{ player.name }}{{ player.isAI ? '（AI）' : '' }}
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
            :title="guardResult.guardBlocked ? `你守住了 ${guardResult.playerName}` : `你守护了 ${guardResult.playerName}`"
            type="success"
            show-icon
          />
        </div>
      </template>

      <!-- 平民：等待 -->
      <template v-else>
        <p>夜间等待中...</p>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';

import type { Player, RoleType } from '@/types/game';
import { ROLE_LABELS } from '@/utils/constants';

const props = defineProps<{
  role: RoleType;
  players: Player[];
  disabled?: boolean;
  currentPlayerId?: string;
  nightResult?: {
    checkedPlayerId?: string | null;
    checkedRole?: RoleType | null;
    guardedPlayerId?: string | null;
    guardBlocked?: boolean;
  } | null;
}>();

const emit = defineEmits<{
  submit: [targetId: string];
}>();

const selectedTarget = ref('');
const roleLabels = ROLE_LABELS;

/** 目标玩家：仅存活的玩家，默认排除自己 */
const targetPlayers = computed(() =>
  props.players.filter((p) => p.isAlive && p.id !== props.currentPlayerId),
);

/** 查验结果显示（仅预言家） */
const checkResult = computed(() => {
  if (props.role !== 'prophet' || !props.nightResult?.checkedPlayerId) return null;
  const target = props.players.find((p) => p.id === props.nightResult!.checkedPlayerId);
  return target ? { playerName: target.name, role: props.nightResult.checkedRole ?? 'unknown' } : null;
});

const guardResult = computed(() => {
  if (props.role !== 'guard' || !props.nightResult?.guardedPlayerId) return null;
  const target = props.players.find((p) => p.id === props.nightResult!.guardedPlayerId);
  return target ? { playerName: target.name, guardBlocked: props.nightResult.guardBlocked ?? false } : null;
});

const handleSubmit = () => {
  if (selectedTarget.value) {
    emit('submit', selectedTarget.value);
    selectedTarget.value = '';
  }
};
</script>

<style scoped>
.night-action {
  margin-bottom: 16px;
}
.check-result {
  margin-top: 12px;
}
</style>
