# WolfBot 项目结构与开发参考

> AI 狼人杀 Web 游戏 — 全栈项目结构速查手册
> 最后更新：2026-05-20（Phase 4：女巫药剂 + 猎人开枪 + 状态机 + 观战模式 + 房间码）

---

## 一、项目概览

| 项 | 值 |
|---|---|
| 项目路径 | `D:\newxiang\WolfBot` |
| 后端框架 | FastAPI + Pydantic + WebSocket |
| 前端框架 | Vue3 + TypeScript + Pinia + Element Plus |
| AI 驱动 | OpenAI 兼容 API（httpx 调用） |
| 默认端口 | 后端 8000 / 前端 5173 |
| 包管理 | 后端 pip / 前端 pnpm |

---

## 二、目录结构总览

```
WolfBot/
├── .workbuddy/memory/          ← AI 工作记忆（跨会话上下文）
├── docs/                       ← 设计文档（Mermaid 图、系统设计）
├── deliverables/               ← 交付物归档
│
├── AI狼人杀（FastAPI+WebSocket）后端技术文档.md
├── AI狼人杀（Vue3全生态）前端技术文档.md
├── 项目构建总文档.md
├── 6人暗牌场.md
├── 开发任务清单.md / 后端开发任务清单.md
│
├── backend/                    ← ===== 后端 =====
│   ├── app/
│   │   ├── main.py             ← FastAPI 应用入口
│   │   ├── core/               ← 核心基础设施
│   │   │   ├── config.py       ← Settings 数据类（环境变量）
│   │   │   ├── exceptions.py   ← AppError 异常定义
│   │   │   └── logging.py      ← 日志配置
│   │   ├── domain/             ← 领域模型（纯数据，无IO）
│   │   │   ├── enums.py        ← GameStatus / RoleType / MessageType
│   │   │   └── roles.py        ← RoleSkill / ScenePreset 注册表
│   │   ├── mode/               ← 游戏模式模块（可插拔）
│   │   │   ├── __init__.py     ← 模式注册表 + get_mode() 导出
│   │   │   └── base.py         ← BaseGameMode + ClassicMode + RoleSelectMode
│   │   ├── schemas/            ← Pydantic 请求/响应模式
│   │   │   ├── base.py         ← BaseSchema（camelCase 别名生成）
│   │   │   ├── game.py         ← 游戏相关 Schema
│   │   │   ├── player.py       ← Player Schema
│   │   │   └── socket.py       ← SocketMessage Schema
│   │   ├── services/           ← 业务逻辑层
│   │   │   ├── game_service.py ← 核心：游戏状态管理、行动记录
│   │   │   ├── judge_service.py← 裁判：流程编排、AI调用、阶段推进
│   │   │   ├── ai_service.py   ← AI 调用（OpenAI兼容API）
│   │   │   ├── vote_service.py ← 投票统计辅助
│   │   │   ├── room_service.py ← 房间管理
│   │   │   ├── result_service.py← 游戏结果
│   │   │   ├── config_service.py← AI配置管理
│   │   │   └── memory_service.py← AI 上下文记忆
│   │   ├── api/
│   │   │   ├── routers/        ← HTTP REST 路由
│   │   │   │   ├── games.py    ← /api/games/{id}/action/* 
│   │   │   │   ├── rooms.py    ← /api/rooms/{id}/*
│   │   │   │   └── health.py   ← /api/health
│   │   │   └── websockets/
│   │   │       └── game_ws.py  ← /ws/game WebSocket 端点
│   │   ├── websocket/          ← WebSocket 基础设施
│   │   │   ├── manager.py      ← ConnectionManager（连接/广播/私发）
│   │   │   └── broadcaster.py  ← 广播器辅助
│   │   ├── utils/              ← 工具函数
│   │   │   ├── ids.py          ← ID 生成
│   │   │   ├── time.py         ← utc_now_iso()
│   │   │   └── validate.py     ← 校验工具
│   │   └── config/
│   │       └── ai_config.json  ← AI 默认配置
│   ├── tests/                  ← 测试
│   │   ├── test_game_flow.py
│   │   └── test_health.py
│   ├── requirements.txt
│   ├── pyproject.toml
│   ├── .env.development / .env.production / .env.example
│
└── frontend/                   ← ===== 前端 =====
    ├── src/
    │   ├── main.ts             ← 应用入口
    │   ├── App.vue             ← 根组件
    │   ├── router/
    │   │   └── index.ts        ← 路由（4个页面 + beforeEach 守卫）
    │   ├── views/              ← 页面视图
    │   │   ├── HomeView.vue    ← 首页（创建/加入房间）
    │   │   ├── GameRoom.vue    ← 房间（座位、设置、开始）
    │   │   ├── GamePlay.vue    ← 游戏（核心页面，集成所有组件）
    │   │   └── GameResult.vue  ← 结果（身份揭示 + 复盘）
    │   ├── components/
    │   │   ├── common/         ← 通用组件
│   │   │   ├── NightAction.vue  ← 夜间行动（狼人杀人/预言家查验/平民等待）
│   │   │   ├── VotePanel.vue    ← 投票面板（含弃票按钮）
│   │   │   ├── ChatBox.vue      ← 聊天框（自动滚动）
│   │   │   ├── Announce.vue     ← 公告展示（自动滚动到最新）
│   │   │   ├── CountdownTimer.vue← 倒计时（支持 totalSeconds 动态进度）
│   │   │   ├── RoleSelect.vue   ← 抢身份面板（倒计时+选择角色）
│   │   │   ├── SheriffElection.vue ← 警长竞选面板（上警/发言/投票/转让）
│   │   │   └── RoleCard.vue     ← 角色卡片
    │   │   └── game/           ← 游戏组件
    │   │       ├── SeatMap.vue      ← 座位图
    │   │       ├── PlayerList.vue   ← 玩家列表
    │   │       └── GameStatus.vue   ← 游戏状态显示
    │   ├── store/
    │   │   ├── index.ts        ← Store 入口
    │   │   └── modules/
    │   │       └── gameStore.ts← Pinia 游戏状态（核心 Store）
    │   ├── hooks/              ← 组合式函数
    │   │   ├── useGameSocket.ts← WebSocket 连接与消息分发
    │   │   └── useGameLogic.ts ← 游戏逻辑辅助
    │   ├── api/                ← HTTP API 封装
    │   │   ├── gameApi.ts      ← REST API 调用（axios）
    │   │   └── socketApi.ts    ← WebSocket URL 构建
    │   ├── types/
    │   │   └── game.ts         ← 所有 TypeScript 类型定义
    │   ├── utils/
    │   │   ├── constants.ts    ← 常量
    │   │   ├── format.ts       ← 格式化工具
    │   │   └── validate.ts     ← 校验工具
    │   └── assets/css/main.css ← 全局样式
    ├── package.json / pnpm-lock.yaml
    ├── vite.config.ts
    ├── tsconfig.json
    ├── .env.development / .env.production / .env.example
    └── dist/                   ← 构建产物
```

---

## 三、核心数据结构

### 3.1 后端枚举

```python
# app/domain/enums.py

class GameStatus(str, Enum):
    waiting = "waiting"       # 等待开始
    role_select = "role_select"  # 抢身份阶段
    night = "night"           # 夜间
    day = "day"               # 白天
    sheriff_election = "sheriff_election"  # 警长竞选
    speak = "speak"           # 发言
    vote = "vote"             # 投票
    end = "end"               # 结束

class RoleType(str, Enum):
    wolf = "wolf"           # 狼人
    civilian = "civilian"   # 平民
    prophet = "prophet"     # 预言家
    guard = "guard"         # 守卫
    hunter = "hunter"       # 猎人
    witch = "witch"         # 女巫
    idiot = "idiot"         # 白痴
    unknown = "unknown"     # 未知（视角隔离）

class MessageType(str, Enum):
    room_update = "room_update"           # 房间更新
    announce = "announce"                 # 系统公告
    ai_speak = "ai_speak"                 # AI 发言
    player_speak = "player_speak"         # 玩家发言
    speak_turn = "speak_turn"             # 发言轮次
    vote_result = "vote_result"           # 单票结果
    vote_summary = "vote_summary"         # 投票汇总
    game_status = "game_status"           # 游戏状态变更
    role_info = "role_info"               # 角色信息
    player_update = "player_update"       # 玩家状态更新
    game_over = "game_over"               # 游戏结束
    night_action = "night_action"         # 夜间行动请求
    night_result = "night_result"         # 夜间结算结果
    wolf_target_update = "wolf_target_update"  # 狼人刀目标实时更新
    role_select_start = "role_select_start"   # 抢身份阶段开始
    role_select_choice = "role_select_choice"  # 抢身份选择（客户端→服务端）
    role_select_result = "role_select_result"  # 抢身份结果
    last_words = "last_words"             # 遗言
    sheriff_elect_start = "sheriff_elect_start"   # 警长竞选开始
    sheriff_campaign = "sheriff_campaign"         # 玩家上警/退选
    sheriff_speech_turn = "sheriff_speech_turn"   # 警长竞选发言轮次
    sheriff_vote = "sheriff_vote"                 # 警长竞选投票
    sheriff_elect_result = "sheriff_elect_result" # 警长竞选结果
    sheriff_transfer = "sheriff_transfer"         # 警长转让徽章
    wolf_self_destruct = "wolf_self_destruct"     # 狼人自爆
    error = "error"                       # 错误消息
```

### 3.2 前端类型（TypeScript）

```typescript
// src/types/game.ts

type GameStatus = 'waiting' | 'role_select' | 'night' | 'day' | 'speak' | 'vote' | 'end';
type RoleType = 'wolf' | 'civilian' | 'prophet' | 'guard' | 'hunter' | 'witch' | 'idiot' | 'unknown';
type ScenePreset = 'six-player-dark' | 'nine-player-dark' | 'twelve-player-dark' | 'twelve-player-standard-dark';
type GameMode = 'classic' | 'role_select';

interface Player {
  id: string; name: string; seatNumber: number;
  role: RoleType; isAI: boolean; isAlive: boolean;
  lastGuardTargetId?: string | null;
}

interface ChatMessage {
  id: string; playerId: string; playerName: string;
  content: string; time: string; isAI: boolean;
}

interface VoteData {
  voterId: string; voterSeat?: number;
  targetId: string; targetSeat?: number;
}

interface WolfTargetUpdate {
  wolfId: string; wolfSeat: number;
  targetId: string; targetSeat: number;
  message: string;
}

interface RoleSelectStartPayload {
  availableRoles: string[];
  timeoutSeconds: number;
  message: string;
  deadline: string;
  totalSeconds: number;
}

interface VoteSummaryPayload { votes: VoteData[]; eliminated: string | null; }

interface NightResultPayload {
  killedPlayerId: string | null;
  guardedPlayerId?: string | null;
  guardBlocked?: boolean;
  checkedResults?: Array<{ playerId: string; targetId: string; isWolf: boolean }>;
  checkedPlayerId: string | null;
  checkedRole: RoleType | null;
}

interface GameSnapshot {
  gameId: string; playerId: string; gameStatus: GameStatus;
  currentRound: number; currentSpeakerId: string | null;
  started: boolean; winnerFaction: string | null;
  players: Player[]; myRole: RoleType;
  nightActionRequired: boolean; roomSettings: RoomSettings;
  ownerPlayerId?: string;
  gameMode?: GameMode;
}

interface GameResultPayload {
  gameId: string; winnerFaction: string; currentRound: number;
  players: Player[]; chats: ChatMessage[]; announcements: string[];
}
```

---

## 四、游戏流程

```
waiting → start_game → [role_select] → night → day → [sheriff_election] → speak → vote → day → speak → vote → ... → end
                            │              │                │                                         │
                            └──────────────┘                │                                         │
                              (仅抢身份模式)               └─ 仅第1轮白天 ──┘                          │
                                                                                                    │
                                              └─ resolve_night ─────────────────────────────────────┘
                                                        └─ resolve_vote_round
```

### 4.1 阶段说明

| 阶段 | 状态 | 行动 | 推进方式 |
|------|------|------|---------|
| 等待 | `waiting` | 选座、配置 | `start_game()` |
| 抢身份 | `role_select` | 选择想要的身份 | 10秒超时后自动结算（仅 `role_select` 模式） |
| 夜间 | `night` | 狼人杀人/预言家查验/守卫守护 | 所有夜间角色提交行动后 `resolve_night()` |
| 白天 | `day` | 公布夜间结果、存活人数 | 自动进入 `sheriff_election`(首日) 或 `speak` |
| 警长竞选 | `sheriff_election` | 上警/竞选发言/投票选举 | 仅首日白天，竞选结束后进入 `speak` |
| 发言 | `speak` | 按座位顺序发言 | 所有人发言后进入 `vote` |
| 投票 | `vote` | 投票/弃票（警长1.5倍票权） | 所有人投票后 `resolve_vote_round()` |
| 结束 | `end` | 展示结果 | 胜负判定后自动 |

> **狼人自爆**：在发言(`speak`)或投票(`vote`)阶段，狼人可随时选择自爆。自爆后跳过当天剩余流程，直接进入下一轮夜晚。

### 4.2 关键函数调用链

```
judge_service.run_game()
  ├── role_select_phase()        ← 仅抢身份模式（10秒窗口+冲突解决）
  ├── _night_phase()
  │     ├── _wait_night_actions()      ← 等待所有夜间行动
  │     ├── _resolve_night()           ← 调用 game_service.resolve_night()
  │     └── _broadcast_night_result()  ← 广播夜间结果（含平安夜/死亡公告）
  ├── _day_phase()
  │     ├── _announce_death()          ← 公布死亡（首夜有遗言，其他天无）
  │     ├── _mode.on_day_start()       ← 模式钩子：公告存活人数等
  │     ├── sheriff_election_phase()   ← 仅第1轮白天：竞选注册→发言→投票→结果
  │     ├── _handle_sheriff_death()    ← 警长死亡时转让徽章
  │     ├── _speak_phase()
  │     │     ├── _wait_human_speak()        ← 等待真人发言
  │     │     ├── _ai_speak()                ← AI 发言
  │     │     └── _broadcast_speak_turn()    ← 通知下一发言者（含 totalSeconds）
  │     └── _vote_phase()
  │           ├── _wait_votes()              ← 等待投票
  │           ├── _resolve_vote()            ← 调用 game_service.resolve_vote_round()（警长1.5倍票权）
  │           └── _announce_vote_result()    ← 公布投票结果（谁投了谁+弃票者）
  │                 └── _handle_sheriff_death()  ← 警长被放逐时转让徽章
```

---

## 五、WebSocket 消息协议

### 5.1 客户端 → 服务端

| message_type | payload | 说明 |
|---|---|---|
| `speak` | `{ content, playerId }` | 玩家发言 |
| `vote` | `{ targetId, playerId }` | 投票（targetId="abstain" 为弃票） |
| `night_action` | `{ targetId, playerId }` | 夜间行动 |
| `role_select_choice` | `{ role, playerId }` | 抢身份选择 |
| `last_words` | `{ content }` | 遗言 |
| `sheriff_campaign` | `{ action: "run"|"withdraw" }` | 警长竞选上警/退选 |
| `sheriff_vote` | `{ targetId }` | 警长竞选投票 |
| `sheriff_transfer` | `{ targetId }` | 警长转让徽章 |
| `wolf_self_destruct` | `{}` | 狼人自爆 |

### 5.2 服务端 → 客户端

| type | payload | 接收者 | 说明 |
|---|---|---|---|
| `room_update` | GameSnapshot | 全体 | 房间状态变更 |
| `announce` | `{ content }` | 全体 | 系统公告 |
| `game_status` | `{ status, round, deadline?, totalSeconds?, gameMode? }` | 全体 | 游戏阶段变更 |
| `role_info` | `{ role, hint?, teammates? }` | 个人 | 角色分配 |
| `speak_turn` | `{ currentSpeakerId, currentSpeakerName, turnIndex, turnCount, deadline, totalSeconds }` | 全体 | 发言轮次 |
| `player_speak` | `{ content, playerId, playerName, isAI }` | 全体 | 玩家发言 |
| `ai_speak` | `{ content, playerId, playerName, isAI }` | 全体 | AI 发言 |
| `vote_result` | `{ targetId, voterId }` | 全体 | 单票结果 |
| `vote_summary` | `{ votes: VoteData[], eliminated }` | 全体 | 投票汇总 |
| `night_action` | `{ actionRequired, deadline?, totalSeconds?, teammates? }` | 个人 | 夜间行动请求/确认 |
| `night_result` | `{ killedPlayerId, guardedPlayerId?, guardBlocked?, checkedResults }` | 个人 | 夜间结算 |
| `wolf_target_update` | `{ wolfId, wolfSeat, targetId, targetSeat, message }` | 狼人队友 | 狼人刀目标实时更新 |
| `role_select_start` | `{ availableRoles, timeoutSeconds, deadline, totalSeconds }` | 全体 | 抢身份阶段开始 |
| `role_select_result` | `{ assignments, message }` | 全体 | 抢身份结果（含分配详情） |
| `last_words` | `{ content, playerId, playerName, isAI }` | 全体 | 遗言消息 |
| `sheriff_elect_start` | `{ phase, deadline, totalSeconds, candidateIds }` | 全体 | 警长竞选开始 |
| `sheriff_campaign` | `{ action, playerId?, playerName?, candidateIds }` | 全体 | 上警/退选通知 |
| `sheriff_speech_turn` | `{ currentSpeakerId, currentSpeakerName, turnIndex, turnCount, deadline, totalSeconds }` | 全体 | 竞选发言轮次 |
| `sheriff_vote` | `{ candidateIds, deadline, totalSeconds }` | 全体 | 警长竞选投票开始 |
| `sheriff_elect_result` | `{ sheriffId, isTie, message }` | 全体 | 警长竞选结果 |
| `sheriff_transfer` | `{ fromPlayerId, toPlayerId?, toPlayerName?, needsChoice?, candidateIds?, deadline?, totalSeconds? }` | 全体/个人 | 警长转让徽章 |
| `wolf_self_destruct` | `{ playerId, playerName, playerRole: "wolf" }` | 全体 | 狼人自爆 |
| `player_update` | `{ playerId, isAlive, playerName }` | 全体 | 玩家状态变更 |
| `game_over` | `{ winnerFaction, ... }` | 全体 | 游戏结束 |
| `error` | `{ content }` | 个人 | 错误消息 |

---

## 六、REST API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/games` | 创建房间 |
| GET | `/api/games/{id}` | 获取游戏快照（支持 ?playerId= 视角隔离） |
| GET | `/api/games/{id}/result` | 获取游戏结果 |
| POST | `/api/games/{id}/action/speak` | 发言 |
| POST | `/api/games/{id}/action/vote` | 投票（targetId="abstain" 弃票） |
| POST | `/api/games/{id}/action/night` | 夜间行动 |
| POST | `/api/rooms/{id}/join` | 加入房间 |
| PUT | `/api/rooms/{id}/seat` | 换座 |
| POST | `/api/rooms/{id}/start` | 开始游戏 |
| GET | `/api/rooms/{id}` | 获取房间信息 |
| PATCH | `/api/rooms/{id}/settings` | 更新房间设置 |
| POST | `/api/rooms/{id}/ai/test` | 测试 AI 连接 |
| GET | `/api/rooms/code/{roomCode}` | 通过房间码查找游戏 |
| POST | `/api/rooms/{id}/spectate` | 观战者加入 |
| GET | `/api/health` | 健康检查 |
| WebSocket | `/ws/game?gameId=&playerId=` | WebSocket 连接 |

---

## 七、前端路由

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | HomeView | 首页：创建/加入房间 |
| `/room/:gameId` | GameRoom | 房间：座位、设置、开始 |
| `/game/:gameId` | GamePlay | 游戏：核心页面 |
| `/result/:gameId` | GameResult | 结果：身份揭示 + 复盘 |

---

## 八、前端 Store 状态（gameStore）

| 字段 | 类型 | 说明 |
|------|------|------|
| `gameId` | `string` | 当前游戏 ID |
| `myId` | `string` | 当前玩家 ID |
| `myRole` | `RoleType` | 当前玩家角色 |
| `gameStatus` | `GameStatus` | 游戏阶段 |
| `currentRound` | `number` | 当前轮次 |
| `currentSpeakerId` | `string \| null` | 当前发言者 |
| `players` | `Player[]` | 玩家列表 |
| `chatMessages` | `ChatMessage[]` | 聊天消息 |
| `announcements` | `AnnounceMessage[]` | 公告列表 |
| `voteSummary` | `VoteSummaryPayload \| null` | 投票汇总 |
| `nightActionRequired` | `boolean` | 是否需要夜间行动 |
| `nightResult` | `NightResultPayload \| null` | 夜间结果 |
| `wolfTeammates` | `string[]` | 狼人队友座位标签 |
| `wolfTargetUpdates` | `WolfTargetUpdate[]` | 狼人队友刀目标实时 |
| `roomSettings` | `RoomSettings` | 房间设置 |
| `deadline` | `string \| null` | 当前阶段截止时间（ISO 8601） |
| `currentPhaseTimeout` | `number` | 当前阶段总倒计时秒数 |
| `roleSelectStart` | `RoleSelectStartPayload \| null` | 抢身份阶段数据 |
| `mySelectedRole` | `string \| null` | 我选择的角色 |
| `gameMode` | `GameMode` | 游戏模式（classic / role_select） |
| `isLastWords` | `boolean` | 是否处于遗言阶段 |
| `sheriffId` | `string \| null` | 当前警长玩家 ID |
| `sheriffCandidateIds` | `string[]` | 警长竞选候选人列表 |
| `sheriffElectStart` | `SheriffElectStartPayload \| null` | 竞选开始数据 |
| `sheriffSpeechTurn` | `SheriffSpeechTurnPayload \| null` | 竞选发言轮次 |
| `sheriffVoteStart` | `SheriffVotePayload \| null` | 竞选投票数据 |
| `sheriffElectResult` | `SheriffElectResultPayload \| null` | 竞选结果 |
| `sheriffTransfer` | `SheriffTransferPayload \| null` | 警长转让数据 |
| `wolfSelfDestructed` | `WolfSelfDestructPayload \| null` | 狼人自爆数据 |

---

## 九、角色技能注册表

| 角色 | 阵营 | 夜间行动 | 行动类型 | 特殊规则 |
|------|------|---------|---------|---------|
| 狼人 | wolf | ✅ | kill | 可自刀 |
| 平民 | civilian | ❌ | — | — |
| 预言家 | civilian | ✅ | check | — |
| 守卫 | civilian | ✅ | guard | 不能连续守同一人 |
| 猎人 | civilian | ❌ | — | 死亡时可开枪 |
| 女巫 | civilian | ✅ | witch | 解药/毒药各一次 |
| 白痴 | civilian | ❌ | — | 被投票放逐时免疫出局，之后不能投票 |

**夜间行动顺序**：狼人 → 预言家 → 女巫 → 守卫

### 场景预设

| 预设 ID | 名称 | 人数 | 角色 |
|---------|------|------|------|
| `six-player-dark` | 6人暗牌场 | 6 | 2狼 + 1预言家 + 1守卫 + 2平民 |
| `nine-player-dark` | 9人暗牌场 | 9 | 3狼 + 1预言家 + 1守卫 + 1猎人 + 3平民 |
| `twelve-player-dark` | 12人暗牌场 | 12 | 4狼 + 1预言家 + 1守卫 + 1女巫 + 1猎人 + 4平民 |
| `twelve-player-standard-dark` | 12人标准暗牌场（预女猎白） | 12 | 4狼 + 1预言家 + 1女巫 + 1猎人 + 1白痴 + 4平民 |

---

## 十、配置项

### 后端环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `API_HOST` | `0.0.0.0` | 监听地址 |
| `API_PORT` | `8000` | 监听端口 |
| `API_PREFIX` | `/api` | API 前缀 |
| `CORS_ORIGINS` | `http://localhost:5173` | CORS 允许源 |
| `AI_API_BASE_URL` | 空 | AI API 地址 |
| `AI_API_KEY` | 空 | AI API 密钥 |
| `AI_MODEL` | `gpt-4o-mini` | 模型名称 |
| `AI_TIMEOUT_SECONDS` | `20` | AI 请求超时 |
| `AI_TEMPERATURE` | `0.7` | 温度参数 |
| `AI_ENABLE_MOCK` | `true` | 是否使用 mock |
| `AI_VOTE_WINDOW_SECONDS` | `5` | AI 投票等待窗口 |
| `AI_SPEAK_WINDOW_SECONDS` | `8` | AI 发言等待窗口 |

### 前端环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VITE_API_BASE_URL` | `http://localhost:8000` | 后端 API 地址 |
| `VITE_WS_URL` | `ws://localhost:8000/ws/game` | WebSocket 地址 |

---

## 十一、关键设计模式

### 11.1 视角隔离

`get_game(game_id, requester_id)` 根据请求者身份过滤返回数据：
- 狼人能看到队友信息
- 预言家能看到自己的查验结果
- 平民只能看到公开信息
- 角色为 `unknown` 除非是自己或队友

### 11.2 命名格式统一

所有玩家显示名统一为 `"{seatNumber}号({name})"` 格式，由后端 `seat_label()` 生成，
WebSocket 消息和 REST API 均使用此格式。

### 11.3 弃票机制

- `targetId = "abstain"` 表示弃票
- 弃票不计入 tally（得票统计）
- 投票汇总和公告中单独展示弃票者

### 11.4 狼人实时通知

狼人提交夜间行动后，后端通过 `wolf_target_update` 消息私发给其他狼人队友，
前端 NightAction 组件实时展示队友的选择。

### 11.5 BaseSchema 别名生成

后端 `BaseSchema` 使用 `alias_generator=to_camel`，Python snake_case 字段
自动映射为前端 camelCase。例如：
- `player_id` → `playerId`
- `seat_number` → `seatNumber`
- `is_ai` → `isAI`

### 11.6 游戏模式系统

`app/mode/` 模块实现可插拔的游戏模式，通过 `BaseGameMode` 抽象基类定义流程钩子：

```
BaseGameMode（抽象基类）
├── ClassicMode      ← 经典模式（随机分配角色）
└── RoleSelectMode   ← 抢身份模式（10秒选角色，冲突随机分配）
```

**钩子方法**：

| 钩子 | 说明 | 默认行为 |
|------|------|---------|
| `allow_role_select` | 属性：是否支持抢身份 | `False` |
| `role_select_timeout_seconds` | 属性：抢身份窗口时长 | `10` |
| `on_game_start()` | 游戏开始时决定初始阶段 | 直接进入夜间 |
| `on_role_select_start(game_id)` | 抢身份阶段开始，返回 payload | — |
| `resolve_role_selection(game_id, selections, available)` | 解决抢身份冲突 | — |
| `on_night_death(game_id, is_first_night)` | 夜间死亡遗言控制 | 首夜有遗言，其他天无 |
| `on_vote_elimination(game_id)` | 投票淘汰遗言控制 | 始终有遗言 |
| `on_day_start(game_id)` | 白天开始额外公告 | 公告存活人数 |

**新增模式**只需继承 `BaseGameMode` + 在 `MODE_REGISTRY` 注册即可，无需修改核心流程代码。
`Judge` 通过 `self._mode` 属性调用钩子。

### 11.7 发言时间精确控制

后端在关键 WebSocket 消息中携带 `totalSeconds` 字段，前端据此动态设置倒计时进度条：
- `speak_turn` 消息：携带 `totalSeconds = speakTimeoutSeconds`
- `game_status(vote)` 消息：携带 `totalSeconds = voteTimeoutSeconds`
- `night_action` 消息：携带 `totalSeconds = nightActionTimeoutSeconds`

### 11.8 状态机校验

后端 `VALID_TRANSITIONS` 定义了合法状态转换，非法转换抛出 409 错误：

| 当前状态 | 可转换到 |
|---------|---------|
| waiting | role_select, night, end |
| role_select | night, end |
| night | day, night, end |
| day | sheriff_election, speak, end |
| sheriff_election | speak, day, end |
| speak | vote, night, end |
| vote | night, end |
| end | —（终态） |

`VALID_ACTIONS` 定义各状态允许的操作，非法操作同样返回 409。

### 11.9 女巫药剂系统

女巫拥有两瓶药剂（各一次使用机会）：
- **解药 (save)**：救活被狼人杀害的目标玩家，优先级高于狼刀结果
- **毒药 (poison)**：直接毒杀一名玩家，不受守卫保护，猎人被毒杀不能开枪

药剂使用追踪：`Player.antidote_used` / `Player.poison_used`

### 11.10 猎人开枪

猎人在以下情况可以开枪带走一人：
- 被狼人夜间杀害 ✅
- 被投票放逐 ✅
- 被女巫毒杀 ❌（不能开枪）

猎人开枪由 `GameState.pending_hunter_shoot` 标记触发，Judge 自动处理 AI 猎人开枪，真人猎人在 WebSocket 中通过 `hunter_shoot` 消息选择目标。

### 11.11 观战模式与房间码

- **房间码**：6位数字，创建房间时自动生成，通过 `GET /api/rooms/code/{room_code}` 查找
- **观战者**：通过 `POST /api/rooms/{game_id}/spectate` 加入，可看到所有角色（上帝视角）

### 11.12 夜间阶段增强

夜间行动顺序：狼人 → 预言家 → 女巫 → 守卫

夜间结算逻辑：
1. 统计狼人刀票 → 确定被杀目标
2. 守卫保护检查（不能连续守同一人）
3. 女巫解药救活被杀目标
4. 女巫毒药毒杀目标
5. 合并死亡列表，标记死亡
6. 猎人死亡检测（被狼杀→可开枪，被毒杀→不可）
7. 检查胜负条件

前端 `gameStore.currentPhaseTimeout` 从后端消息动态更新，不再硬取 `speakTimeoutSeconds`。

### 11.8 遗言规则

- **夜间死亡**：仅首夜（第1轮）有遗言，后续夜晚无遗言（通过 `on_night_death` 钩子控制）
- **投票淘汰**：始终有遗言（通过 `on_vote_elimination` 钩子控制）
- 遗言规则可通过自定义模式覆写钩子修改
- 遗言通过 WebSocket `last_words` 消息类型发送，前端通过 `isLastWords` 标记区分遗言和普通发言

### 11.9 白痴翻牌免疫

- 白痴被投票放逐时自动翻牌，免疫出局
- 翻牌后标记 `vote_immunity_used = True`，之后不能再参与投票
- 被狼人杀害或被女巫毒杀时无法免疫，正常死亡
- Player 模型新增 `vote_immunity_used` 字段

### 11.10 警长机制

- **竞选流程**：首日白天前进入 `sheriff_election` 阶段
  - 5秒上警窗口：存活玩家选择是否上警
  - 竞选发言：候选人按座位顺序发表竞选演说
  - 投票选举：非候选人投票（弃权可选）
  - 结果公告：得票最高者当选，平票则无人当选
- **警长权利**：
  - 投票时票权为1.5倍（`resolve_vote_round` 中 weight=1.5）
  - 警长标识在玩家列表中显示（`is_sheriff` 字段）
- **警长死亡**：
  - 夜间被杀或被投票放逐时触发 `_handle_sheriff_death()`
  - AI 警长自动转让给存活好人
  - 真人警长选择继承人（30秒超时自动转让）
  - 通过 `sheriff_transfer` 消息类型处理
- **GameState 新增字段**：`sheriff_id`, `sheriff_candidate_ids`, `sheriff_votes`, `sheriff_campaign_submitted`
- **Player 新增字段**：`is_sheriff`
- **GameSnapshot 新增字段**：`sheriff_id`, `sheriff_candidate_ids`
- **竞选发言**：复用 `record_speak()` 发言记录，通过 `sheriff_campaign_submitted` 标记区分

### 11.11 狼人自爆机制

- **触发条件**：存活狼人在白天发言(`speak`)或投票(`vote`)阶段可自爆
- **自爆流程**：
  1. 狼人发送 `wolf_self_destruct` WebSocket 消息
  2. `game_service.wolf_self_destruct()` 校验并标记死亡
  3. `judge_service._handle_wolf_self_destruct()` 处理：
     - 公告自爆 + 广播 `wolf_self_destruct` + `player_update`
     - 自爆狼人发表遗言
     - 警长转让（如自爆者是警长）
     - 跳过剩余白天流程，直接进入下一轮夜晚
- **AI 狼人自爆决策**：
  - 只剩1狼时不自爆（自爆即输）
  - 好人数量≥3倍狼人时 8% 概率自爆
  - 默认 2% 概率自爆
- **GameState 新增字段**：`wolf_self_destructed`
- **前端**：GamePlay.vue 中 speak/vote 阶段显示自爆按钮（仅狼人可见，含确认对话框）
- **注意**：自爆后 `game.current_round += 1`，直接进入夜晚

---

## 十二、开发命令

```bash
# 后端
cd D:\newxiang\WolfBot\backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd D:\newxiang\WolfBot\frontend
pnpm install
pnpm dev              # 开发服务器
pnpm build            # 构建
npx vue-tsc --noEmit  # 类型检查

# 后端编译检查
python -c "import py_compile; py_compile.compile('app/services/game_service.py', doraise=True)"
```

---

## 十三、已实现功能清单

### 基础功能
- [x] 创建/加入房间
- [x] 座位选择与换座
- [x] 房间设置（场景预设、AI配置）
- [x] 游戏流程（night→day→speak→vote 循环）
- [x] 视角隔离（按角色过滤数据）
- [x] WebSocket 实时通信
- [x] AI 自动发言/投票/夜间行动
- [x] 游戏结果与复盘

### 功能增强（2026-05-20 第一批）
- [x] 狼人刀目标实时显示给队友
- [x] 投票弃票功能
- [x] 用户名格式统一为"几号(玩家名)"
- [x] 聊天界面自动滚动
- [x] 玩家发送的消息也显示在聊天中
- [x] 复盘摘要增加谁杀了谁
- [x] 投票公告显示谁投了谁、谁弃票了

### 功能增强（2026-05-20 第二批）
- [x] 抢身份模式（开局10秒选角色，多人抢同一角色随机分配）
- [x] 修复发言时间不一致Bug（后端消息带totalSeconds，前端动态获取）
- [x] 系统公告自动滚动到最新
- [x] 夜间死亡遗言仅首夜，其他天无遗言
- [x] 投票淘汰遗言保持不变
- [x] 白天公告存活人数
- [x] 游戏模式模块化（BaseGameMode + ClassicMode + RoleSelectMode）
- [x] 场景预设新增 mode 字段选择模式

### Bug修复（2025-07-27）
- [x] ai_service.py 移除多余的 advance_round() 调用
- [x] useGameSocket.ts night_result 从 checkedResults 解析当前玩家结果
- [x] game_service.py record_vote() 禁止投自己
- [x] NightAction.vue targetPlayers 过滤掉自己
- [x] GameRoom.vue getRoom() 传入 playerId
- [x] test_game_flow.py 断言修正

### Bug修复与功能增强（2026-05-20 第五批）
- [x] 修复抢身份后角色丢失：useGameSocket.ts ROLE_TYPES 数组补充 hunter/witch/idiot
- [x] 修复遗言无法发送：前端增加 isLastWords 状态，通过 WebSocket last_words 消息发送
- [x] 修复 canNightAction 缺少 witch 角色
- [x] 新增白痴角色（idiot）：翻牌免疫投票出局，之后不能投票
- [x] 新增12人标准暗牌场预设（预女猎白）：4狼+1预言家+1女巫+1猎人+1白痴+4平民
- [x] NightAction.vue 添加女巫夜间行动模板

### 功能增强（2026-05-20 Phase 2：警长机制 + 狼人自爆）
- [x] 警长竞选阶段（sheriff_election）：上警→竞选发言→投票选举
- [x] 警长1.5倍票权（resolve_vote_round 中 weight 计算）
- [x] 警长死亡转让徽章（AI自动选择/真人手动选择）
- [x] Player 新增 is_sheriff 字段，PlayerList 显示🏅标识
- [x] SheriffElection.vue 竞选面板组件
- [x] GameState 新增 sheriff_id/sheriff_candidate_ids/sheriff_votes 等字段
- [x] 6个新 WebSocket 消息类型：sheriff_elect_start/sheriff_campaign/sheriff_speech_turn/sheriff_vote/sheriff_elect_result/sheriff_transfer
- [x] 狼人自爆机制：speak/vote 阶段狼人可自爆，跳过白天直接进夜
- [x] AI 狼人自爆决策（剩余1狼不自爆，好人优势大时8%概率）
- [x] 前端狼人自爆按钮（确认对话框防误触）
- [x] GameState 新增 wolf_self_destructed 字段
- [x] 新增 wolf_self_destruct WebSocket 消息类型

---

## 十四、常见修改场景速查

| 需求 | 修改文件 |
|------|---------|
| 新增 WebSocket 消息类型 | `enums.py` + `game.ts` + `useGameSocket.ts` + `game_ws.py` |
| 新增 REST API 端点 | `games.py` 或 `rooms.py` + `gameApi.ts` |
| 修改游戏流程/阶段逻辑 | `judge_service.py` + `game_service.py` |
| 修改前端页面布局 | `views/*.vue` |
| 修改组件行为 | `components/common/*.vue` 或 `components/game/*.vue` |
| 新增角色 | `roles.py`（注册 RoleSkill）+ `enums.py`（新增 RoleType）+ `game.ts` + `constants.ts` + `useGameSocket.ts`（ROLE_TYPES）+ `RoleSelect.vue`（ROLE_INFO） |
| 新增场景预设 | `roles.py`（SCENE_PRESETS） |
| 新增游戏模式 | `mode/base.py`（继承 BaseGameMode + 注册 MODE_REGISTRY） |
| 修改 Store 状态 | `gameStore.ts` + `game.ts`（类型） |
| 修改 AI 行为 | `ai_service.py` |
| 修改配置项 | `config.py` + `.env.*` |
| 修改遗言规则 | `mode/base.py`（覆写 on_night_death / on_vote_elimination 钩子） |
