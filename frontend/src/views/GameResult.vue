<template>
  <div class="page-shell">
    <el-card>
      <template #header>结算结果</template>
      <p>这里展示胜负结果、阵营与复盘摘要。</p>
      <el-button @click="$router.push({ name: 'home' })">返回首页</el-button>
    </el-card>
  </div>
</template>
