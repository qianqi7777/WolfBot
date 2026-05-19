<template>
  <el-card shadow="never">
    <template #header>发言记录</template>
    <div class="chat-box">
      <div v-for="item in messages" :key="item.id" class="chat-item">
        <strong>{{ item.playerName }}</strong>
        <span>{{ item.content }}</span>
        <small>{{ item.time }}</small>
      </div>
    </div>
    <el-input v-model="draft" type="textarea" :rows="3" placeholder="输入发言" />
    <div class="actions">
      <el-button type="primary" :disabled="!draft.trim()" @click="$emit('submit', draft)">发送</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  messages: Array<{ id: string; playerName: string; content: string; time: string }>;
}>();

defineEmits<{
  submit: [content: string];
}>();

const draft = defineModel<string>('draft', { default: '' });
</script>
