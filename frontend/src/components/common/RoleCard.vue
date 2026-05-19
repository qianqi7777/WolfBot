<template>
  <el-card shadow="never" class="role-card">
    <template #header>我的身份</template>
    <div>{{ label }}</div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import type { RoleType } from '@/types/game';
import { ROLE_LABELS } from '@/utils/constants';

const props = defineProps<{ role: RoleType }>();

const label = computed(() => ROLE_LABELS[props.role]);
</script>
