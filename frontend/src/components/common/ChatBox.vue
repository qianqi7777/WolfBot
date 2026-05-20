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
    <el-input v-model="draft" type="textarea" :rows="3" placeholder="输入发言" :disabled="disabled" />
    <div class="actions">
      <el-button type="primary" :disabled="disabled || !draft.trim()" @click="handleSend">发送</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
const props = defineProps<{
  messages: Array<{ id: string; playerName: string; content: string; time: string }>;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  submit: [content: string];
}>();

const draft = defineModel<string>('draft', { default: '' });

const handleSend = () => {
  if (props.disabled || !draft.value.trim()) return;
  emit('submit', draft.value);
  draft.value = '';
};
</script>

<style scoped>
.chat-box {
  max-height: 300px;
  overflow-y: auto;
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
  padding-right: 4px;
}

.chat-item {
  display: grid;
  gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid #eef2f7;
}
</style>
