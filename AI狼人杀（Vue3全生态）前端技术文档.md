# AI狼人杀（Vue3全生态）前端技术文档

## 文档说明

本文档为 AI狼人杀纯文字网页版（前端）技术方案，基于 Vue3 全生态开发，严格遵循「前后端彻底分离」原则，完全适配独立服务端（FastAPI \+ WebSocket），支持后续无缝扩展语音功能、原生客户端、多玩家联机等需求，可直接交付开发人员（或AI）落地实现，无需额外补充需求。

## 一、项目核心定位

1. 当前版本：纯文字交互网页端，支持 1 名真人玩家与 4\~5 名 AI 智能体完成狼人杀全流程（身份分配、夜间行动、文字发言、投票淘汰、胜负判定），无语音功能，优先实现核心玩法。

2. 架构适配：前端仅负责「视图展示 \+ 用户交互 \+ 数据渲染」，所有游戏核心逻辑（规则、AI 决策、流程管控）均由后端提供，与后端通过 REST 接口 \+ WebSocket 通信，彻底解耦。

3. 扩展预留：代码结构按工业级标准设计，后续新增语音功能、原生客户端（PC/移动端）、多真人联机、游戏复盘等功能时，无需重构核心代码，仅需新增模块即可。

## 二、技术栈详情（Vue3 全生态，固定无歧义）

|技术模块|具体选型|版本建议|核心作用|
|---|---|---|---|
|核心框架|Vue3 \+ Vite|Vue 3\.4\.x、Vite 5\.0\.x|前端基础框架，实现组件化开发、高效构建，适配现代浏览器|
|类型安全|TypeScript|5\.2\.x|提供类型约束，杜绝类型错误，提升代码可维护性，方便后期扩展与多人协作|
|状态管理|Pinia|2\.1\.x|全局管理游戏状态（身份、发言记录、投票数据、游戏流程），实现组件间数据共享|
|UI 组件库|Element Plus|2\.7\.x|快速搭建规范、美观的 UI 界面（聊天框、投票面板、弹窗、布局等），减少重复开发|
|通信工具|Axios \+ 自定义 WebSocket Hook|Axios 1\.6\.x|对接后端 REST 接口（创建游戏、加入游戏）、WebSocket 实时通信（发言、投票、公告推送）|
|路由管理|Vue Router|4\.3\.x|实现多页面跳转（首页、游戏房间、对局界面、结算复盘页），管理页面路由逻辑|
|代码规范|ESLint \+ Prettier|ESLint 8\.50\.x、Prettier 3\.0\.x|统一代码格式，避免混乱，提升代码可读性和可维护性|
|构建部署|Vite \+ 静态资源托管|\-|打包前端项目，支持本地测试、服务器部署，适配网页端访问|

### 选型说明

所有选型均遵循「成熟稳定、易扩展、低成本」原则，国内开发环境适配性强，且生态完善，开发人员（或AI）可快速上手，后续扩展语音、跨端功能时无需更换技术栈。

## 三、整体架构设计（前后端分离，高可扩展）

### 3\.1 分层架构（自上而下，解耦清晰）

```plain text
前端架构（Vue3全生态）
├─ 视图层（View）：页面与UI组件，负责展示数据、接收用户操作
├─ 状态层（Store）：Pinia全局状态，管理游戏核心数据，实现组件间数据互通
├─ 通信层（Communication）：封装Axios、WebSocket，统一对接后端接口
├─ 工具层（Utils）：通用工具函数，后续可扩展语音SDK、日志处理、数据校验
└─ 路由层（Router）：管理页面跳转，控制访问权限（如未加入游戏无法进入对局页）
```

### 3\.2 项目目录结构（标准化，可直接复制搭建）

```plain text
src/
├── api/                  # 接口封装（后端对接核心）
│   ├── gameApi.ts        # REST接口封装（创建游戏、加入游戏、获取游戏状态）
│   └── socketApi.ts      # WebSocket封装（实时通信：发言、投票、公告）
├── hooks/                # 自定义Hook（复用逻辑）
│   ├── useGameSocket.ts  # 游戏专用WebSocket Hook（核心，封装连接、发送、接收逻辑）
│   └── useGameLogic.ts   # 游戏逻辑辅助Hook（如发言校验、投票状态控制）
├── store/                # Pinia全局状态管理
│   ├── index.ts          # Pinia实例创建
│   └── modules/
│       └── gameStore.ts  # 游戏核心状态（身份、发言、投票、流程）
├── components/           # 可复用UI组件（全局通用，支持后期复用扩展）
│   ├── common/           # 基础通用组件
│   │   ├── ChatBox.vue   # 文字聊天框（展示玩家/AI发言，支持用户输入）
│   │   ├── VotePanel.vue # 投票面板（展示玩家列表，支持点击投票）
│   │   ├── RoleCard.vue  # 身份卡片（仅自己可见，展示当前身份）
│   │   └── Announce.vue  # 游戏公告栏（展示昼夜切换、淘汰结果等）
│   └── game/             # 游戏专用组件
│       ├── PlayerList.vue# 玩家列表（展示所有玩家+AI，标注状态）
│       └── GameStatus.vue# 游戏状态提示（当前阶段：夜间/发言/投票）
├── views/                # 页面组件（对应路由）
│   ├── HomeView.vue      # 首页（创建游戏、加入游戏入口）
│   ├── GameRoom.vue      # 游戏房间（等待开局、展示玩家信息）
│   ├── GamePlay.vue      # 对局界面（核心页面：发言、投票、游戏流程展示）
│   └── GameResult.vue    # 结算页面（展示胜负结果、复盘入口）
├── utils/                # 工具函数（通用复用）
│   ├── format.ts         # 数据格式化（如时间、发言内容）
│   ├── validate.ts       # 校验函数（如发言长度、投票合法性）
│   └── constants.ts      # 常量定义（如游戏阶段、角色类型）
├── router/               # 路由配置
│   └── index.ts          # 路由规则、路由守卫（控制页面访问权限）
├── types/                # TypeScript类型定义（全局复用）
│   └── game.ts           # 游戏相关类型（玩家、发言、投票、游戏状态等）
├── assets/               # 静态资源（图片、样式）
│   ├── css/              # 全局样式
│   └── images/           # 角色头像、游戏图标（后续可扩展）
├── App.vue               # 根组件（页面布局容器）
├── main.ts               # 入口文件（初始化Vue、Pinia、Router、WebSocket）
├── vite.config.ts        # Vite配置（打包、代理、环境变量）
├── .eslintrc.js          # ESLint配置
└── .prettierrc.js        # Prettier配置
```

## 四、核心模块实现（详细代码\+逻辑，可直接开发）

### 4\.1 TypeScript 类型定义（types/game\.ts）

统一游戏相关数据类型，避免类型错误，所有接口、状态均基于此类型开发：

```typescript
// 游戏阶段类型
export type GameStatus = "waiting" | "night" | "day" | "speak" | "vote" | "end";

// 角色类型
export type RoleType = "wolf" | "civilian" | "prophet" | "unknown";

// 玩家类型（真人+AI）
export interface Player {
  id: string; // 玩家唯一ID
  name: string; // 玩家名称（AI自动生成，真人可自定义）
  role: RoleType; // 角色
  isAI: boolean; // 是否为AI
  isAlive: boolean; // 是否存活
}

// 发言记录类型
export interface ChatMessage {
  id: string;
  playerId: string;
  playerName: string;
  content: string; // 文字发言内容
  time: string; // 发言时间
  isAI: boolean;
}

// 投票数据类型
export interface VoteData {
  voterId: string; // 投票者ID
  targetId: string; // 被投票者ID
}

// WebSocket消息类型
export interface SocketMessage {
  type: "announce" | "ai_speak" | "vote_result" | "game_status" | "role_info";
  content?: string;
  player?: string;
  data?: any;
}
```

### 4\.2 全局状态管理（store/modules/gameStore\.ts）

用 Pinia 管理游戏全局状态，所有组件可直接调用/修改，支持后续扩展：

```typescript
import { defineStore } from "pinia";
import { GameStatus, RoleType, Player, ChatMessage, VoteData } from "@/types/game";

export const useGameStore = defineStore("game", {
  state: (): {
    gameId: string; // 当前游戏ID
    gameStatus: GameStatus; // 游戏阶段
    myRole: RoleType; // 自己的身份（仅自己可见）
    myId: string; // 自己的玩家ID
    players: Player[]; // 所有玩家（真人+AI）
    chatList: ChatMessage[]; // 文字发言记录
    voteList: VoteData[]; // 投票记录
    announceList: string[]; // 游戏公告记录
  } => ({
    gameId: "",
    gameStatus: "waiting",
    myRole: "unknown",
    myId: "",
    players: [],
    chatList: [],
    voteList: [],
    announceList: [],
  }),
  actions: {
    // 初始化游戏（创建/加入游戏后调用）
    initGame(gameId: string, myId: string, players: Player[]) {
      this.gameId = gameId;
      this.myId = myId;
      this.players = players;
      this.chatList = [];
      this.voteList = [];
      this.announceList = [];
      this.gameStatus = "waiting";
    },

    // 设置自己的身份（后端推送后调用）
    setMyRole(role: RoleType) {
      this.myRole = role;
    },

    // 更新游戏阶段
    setGameStatus(status: GameStatus) {
      this.gameStatus = status;
    },

    // 添加发言记录（玩家/AI发言通用）
    addChatMessage(message: ChatMessage) {
      this.chatList.push(message);
    },

    // 添加投票记录
    addVote(vote: VoteData) {
      this.voteList.push(vote);
    },

    // 添加游戏公告
    addAnnounce(content: string) {
      this.announceList.push(`[${new Date().toLocaleTimeString()}] ${content}`);
    },

    // 更新玩家状态（如淘汰、存活）
    updatePlayerStatus(playerId: string, isAlive: boolean) {
      const player = this.players.find((p) => p.id === playerId);
      if (player) player.isAlive = isAlive;
    },

    // 重置游戏（重新开局用）
    resetGame() {
      this.gameId = "";
      this.gameStatus = "waiting";
      this.myRole = "unknown";
      this.myId = "";
      this.players = [];
      this.chatList = [];
      this.voteList = [];
      this.announceList = [];
    },
  },
});
```

### 4\.3 WebSocket 封装（hooks/useGameSocket\.ts）

统一封装 WebSocket 通信逻辑，适配游戏实时交互，后续扩展语音时无需修改底层：

```typescript
import { ref, onMounted, onUnmounted } from "vue";
import { useGameStore } from "@/store/modules/gameStore";
import { SocketMessage, VoteData } from "@/types/game";

export function useGameSocket() {
  const socket = ref<WebSocket | null>(null);
  const isConnected = ref(false); // WebSocket连接状态
  const gameStore = useGameStore();
  const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/game"; // 后端WebSocket地址

  // 连接WebSocket
  const connect = (gameId: string, playerId: string) => {
    // 关闭现有连接（防止重复连接）
    if (socket.value) {
      socket.value.close();
    }

    // 建立新连接（携带游戏ID、玩家ID）
    socket.value = new WebSocket(`${WS_URL}?gameId=${gameId}&playerId=${playerId}`);

    // 连接成功
    socket.value.onopen = () => {
      console.log("WebSocket连接成功");
      isConnected.value = true;
    };

    // 接收后端消息（统一处理）
    socket.value.onmessage = (event) => {
      const message: SocketMessage = JSON.parse(event.data);
      handleSocketMessage(message);
    };

    // 连接关闭
    socket.value.onclose = () => {
      console.log("WebSocket连接关闭");
      isConnected.value = false;
      // 重连逻辑
```

> （注：文档部分内容可能由 AI 生成）
