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

      <!-- 女巫：看到刀口，选择是否救 + 选毒杀目标 -->
      <template v-else-if="role === 'witch'">
        <!-- 解药：显示刀口，选择救/不救 -->
        <div v-if="!antidoteUsed" class="witch-save-section">
          <el-alert
            :title="wolfKillInfo"
            type="warning"
            show-icon
            :closable="false"
            style="margin-bottom: 12px"
          />
          <p>是否使用解药？</p>
          <div class="potion-select">
            <el-radio-group v-model="potionType" :disabled="disabled" size="large">
              <el-radio-button value="save">
                💚 使用解药（救活{{ wolfKillLabel }}）
              </el-radio-button>
              <el-radio-button value="skip">
                ⏭️ 不使用解药
              </el-radio-button>
            </el-radio-group>
          </div>
        </div>
        <div v-else class="witch-save-section">
          <el-alert title="解药已使用" type="info" show-icon :closable="false" class="used-alert" />
        </div>
        <!-- 毒药：选择毒杀目标 -->
        <div v-if="!poisonUsed" class="witch-poison-section">
          <el-divider />
          <p>毒药：选择要毒杀的玩家</p>
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
            v-if="!poisonSubmitted"
            type="danger"
            :disabled="disabled || !selectedTarget"
            style="margin-top: 8px"
            size="small"
            @click="handlePoisonSubmit"
          >
            确认毒杀
          </el-button>
          <el-tag v-else type="danger" size="small" style="margin-top: 8px">毒杀已提交</el-tag>
        </div>
        <div v-else class="witch-poison-section">
          <el-alert title="毒药已使用" type="info" show-icon :closable="false" class="used-alert" />
        </div>
        <!-- 确认解药/跳过 -->
        <el-button
          v-if="potionType && potionType !== 'poison' && !saveSubmitted"
          type="warning"
          :disabled="disabled"
          style="margin-top: 12px"
          @click="handleSaveSubmit"
        >
          {{ potionType === 'save' ? '确认使用解药' : '确认跳过' }}
        </el-button>
        <el-tag v-if="saveSubmitted" type="success" size="small" style="margin-top: 12px">解药操作已提交</el-tag>
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
  wolfKillTargetId?: string | null;
  wolfKillTargetLabel?: string;
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

/** 狼人刀口信息 */
const wolfKillLabel = computed(() => props.wolfKillTargetLabel || '未知');
const wolfKillInfo = computed(() =>
  props.wolfKillTargetId
    ? `⚠️ 狼人今晚袭击了 ${wolfKillLabel.value}`
    : '今晚无人被刀',
);

/** 目标玩家：仅存活的玩家，狼人和女巫毒药可以选自己（毒药不限制自毒，由后端校验） */
const targetPlayers = computed(() => {
  const canTargetSelf = props.role === 'wolf';
  return props.players.filter(
    (p) => p.isAlive && (canTargetSelf || p.id !== props.currentPlayerId),
  );
});

const saveSubmitted = ref(false);
const poisonSubmitted = ref(false);

const handleSaveSubmit = () => {
  if (potionType.value === 'save' && props.wolfKillTargetId) {
    emit('submit', props.wolfKillTargetId, 'save');
    saveSubmitted.value = true;
  } else if (potionType.value === 'skip') {
    // 跳过解药：提交一个空操作
    emit('submit', '', '');
    saveSubmitted.value = true;
  }
};

const handlePoisonSubmit = () => {
  if (selectedTarget.value) {
    emit('submit', selectedTarget.value, 'poison');
    poisonSubmitted.value = true;
  }
};

/** 查验结果显示（暂从 announce 获取） */
const checkResult = computed(() => {
  // TODO: Phase 2 从私发 announce 解析查验结果
  return null;
});

const guardResult = computed(() => {
  if (props.role !== 'guard' || !props.nightResult?.guardedPlayerId) return null;
  const target = props.players.find((p) => p.id === props.nightResult!.guardedPlayerId);
  return target ? { seatLabel: `${target.seatNumber}号`, guardBlocked: props.nightResult.guardBlocked ?? false } : null;
});
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
