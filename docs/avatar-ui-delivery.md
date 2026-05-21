# WolfBot 头像系统与前端 UI 改造 — 交付文档

> 交付日期：2026-05-21 | 主理人：齐活林（Qi）

---

## TL;DR

为 WolfBot AI 狼人杀 Web 游戏增加了完整的头像系统，并将前端界面大改为网易狼人杀风格的圆桌布局，包括昼夜主题切换、聊天气泡、角色卡片升级等。

---

## 交付概览

| 项目 | 状态 |
|------|------|
| 头像系统 | ✅ 完成 |
| 圆桌布局 | ✅ 完成 |
| 聊天气泡 | ✅ 完成 |
| 角色卡片升级 | ✅ 完成 |
| 昼夜主题 | ✅ 完成 |
| 死亡标识 | ✅ 完成 |
| 发言高亮动画 | ✅ 完成 |
| TypeScript 编译 | ✅ 通过 |
| Vite 构建 | ✅ 通过 |

---

## 新增文件清单（18 个）

### 前端 - SVG 资源（12 个）

| 文件 | 说明 |
|------|------|
| `frontend/src/assets/avatars/avatar-human.svg` | 真人默认头像（简约人形轮廓） |
| `frontend/src/assets/avatars/avatar-ai.svg` | AI 机器人头像（芯片/机器人风格） |
| `frontend/src/assets/avatars/role-wolf.svg` | 狼人角色图标 |
| `frontend/src/assets/avatars/role-civilian.svg` | 平民角色图标 |
| `frontend/src/assets/avatars/role-prophet.svg` | 预言家角色图标 |
| `frontend/src/assets/avatars/role-guard.svg` | 守卫角色图标 |
| `frontend/src/assets/avatars/role-hunter.svg` | 猎人角色图标 |
| `frontend/src/assets/avatars/role-witch.svg` | 女巫角色图标 |
| `frontend/src/assets/avatars/role-idiot.svg` | 白痴角色图标 |
| `frontend/src/assets/avatars/role-unknown.svg` | 未知角色图标 |
| `frontend/src/assets/avatars/badge-sheriff.svg` | 警长金色星星徽章 |
| `frontend/src/assets/avatars/badge-dead.svg` | 死亡红色X标记 |

### 前端 - 组件（4 个）

| 文件 | 说明 |
|------|------|
| `frontend/src/components/game/PlayerSeat.vue` | 单个座位卡片（头像+名字+状态角标+发言动画） |
| `frontend/src/components/game/CircleTable.vue` | 圆桌容器（环形排列玩家座位） |
| `frontend/src/components/common/ChatBubble.vue` | 聊天气泡组件（自己/他人/AI三种样式） |
| `frontend/src/components/common/RoleIcon.vue` | 角色图标组件（根据RoleType渲染SVG） |

### 前端 - 工具与样式（3 个）

| 文件 | 说明 |
|------|------|
| `frontend/src/utils/avatar.ts` | 头像计算工具（getPlayerAvatar / getDefaultAvatar） |
| `frontend/src/styles/theme-light.css` | 浅色主题 CSS 变量 |
| `frontend/src/styles/theme-dark.css` | 暗色主题 CSS 变量 + Element Plus 组件暗色覆盖 |

---

## 修改文件清单（8 个）

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/types/game.ts` | Player 接口增加 `avatarUrl?: string` |
| `frontend/src/utils/constants.ts` | 增加 `ROLE_FACTION` / `FACTION_LABELS` / `ROLE_SKILL_DESC` 常量 |
| `frontend/src/assets/css/main.css` | 引入 theme-light.css 和 theme-dark.css |
| `frontend/src/components/game/PlayerList.vue` | 重写：从 el-tag 列表 → CircleTable + PlayerSeat 环形布局 |
| `frontend/src/components/common/ChatBox.vue` | 重写：加入 ChatBubble 气泡样式 + 头像 + 自己/AI/他人区分 |
| `frontend/src/components/common/RoleCard.vue` | 重写：角色图标 + 阵营标签 + 技能描述 |
| `frontend/src/views/GamePlay.vue` | 重写：三段式布局（顶栏+圆桌+底部操作栏）+ 暗色主题切换 |
| `backend/app/schemas/player.py` | 增加 `avatar_url: str | None` 字段 |

---

## 核心功能说明

### 1. 头像系统

- **真人默认头像**：简约人形轮廓，灰色调圆形
- **AI 机器人头像**：蓝色芯片/机器人风格，方形圆角，与真人明显区分
- **自定义头像**：Player 模型预留 `avatarUrl` 字段，为后续上传功能预留
- **头像计算逻辑**：统一通过 `avatar.ts` 工具函数，优先级：avatarUrl > isAI ? AI头像 : 真人头像

### 2. 圆桌环形布局

- **CircleTable 容器**：将玩家座位围成环形排列
- **PlayerSeat 组件**：每个座位显示圆形头像(64×64) + 座位号徽章 + 名字 + AI标签
- **排列算法**：自己固定在6点钟（正下方），其余按座位号顺时针排列
- **CSS 定位**：`transform: translate(x%, y%)` 基于椭圆角度计算
- **观战者不参与**环形排列

### 3. 发言者高亮动画

- 当前发言玩家头像外圈蓝色脉冲动画（`@keyframes pulse-glow`）
- 动画周期 1.5s，box-shadow 扩散与收回
- 暗色主题下发光色自动变为 `#60a5fa`

### 4. 死亡玩家视觉标识

- 头像 `filter: grayscale(1) opacity(0.5)` 灰度半透明
- 右下角叠加红色✕死亡标记（badge-dead.svg）
- 边框变灰

### 5. 聊天气泡

- **自己消息**：靠右对齐，蓝色气泡，右侧显示头像
- **他人消息**：靠左对齐，灰色气泡，左侧显示头像
- **AI 消息**：靠左对齐，紫色气泡，左侧显示AI机器人头像，名字旁有"AI"标识
- 气泡使用 CSS 变量适配暗色主题

### 6. 角色卡片升级

- 显示角色图标 + 角色名 + 阵营标签（狼人=红色/好人=绿色）+ 技能描述
- 未分配角色时显示"身份未分配"占位

### 7. 昼夜主题切换

- 白天：浅色主题（默认 Element Plus 色调）
- 夜间：暗色主题（深蓝背景 #1a1a2e → #16213e 渐变）
- 切换通过 `data-theme="dark"` 属性 + CSS 变量实现
- 过渡动画 `transition: all 0.5s ease`
- 暗色下圆桌区域显示径向渐变背景（模拟星空）
- Element Plus 组件通过 `--el-*` 变量覆盖适配暗色

### 8. GamePlay 布局重构

- **旧布局**：CSS Grid 两栏（左操作区 + 右信息流）
- **新布局**：Flexbox 三段式
  - 顶栏：GameStatus + CountdownTimer + RoleCard
  - 中央：CircleTable（环形玩家座位）+ 中央浮动（发言提示+系统公告）
  - 底部：ChatBox + 操作面板（NightAction/VotePanel等），sticky定位

---

## 狼人自爆按钮修复

- 前端 `canWolfSelfDestruct` 条件增加 `sheriff_election` 阶段
- 与后端之前修改的"竞选阶段允许自爆"逻辑保持一致

---

## 用户下一步建议

1. **启动项目**：`cd frontend && npm run dev` 启动前端开发服务器
2. **检查暗色主题**：进入游戏后观察夜间阶段的暗色效果是否自然
3. **验证6/9/12人布局**：创建不同人数的房间，检查环形排列效果
4. **后续扩展**：可考虑添加自定义头像上传功能（后端需增加存储支持）
5. **移动端适配**：当前仅保证桌面端，移动端圆桌布局需要额外适配
