# AI狼人杀（FastAPI+WebSocket）后端技术文档

## 文档说明

本文档面向 AI狼人杀 纯文字网页版的后端服务，基于 FastAPI + WebSocket 构建，严格遵循前后端彻底分离原则。后端负责房间管理、身份分配、流程控制、AI 决策、投票裁决、胜负判定和实时消息推送，前端只消费后端输出的数据。

## 一、项目核心定位

1. 当前版本服务于 1 名真人玩家与 4 到 5 名 AI 的纯文字狼人杀对局，支持创建房间、加入房间、阶段流转、发言、投票、结算全流程。

2. 后端是整个对局规则的唯一可信来源，所有身份、阶段、投票、淘汰和胜负逻辑都在后端执行，避免前端侧重复实现业务裁决。

3. 架构预留扩展能力，后续可平滑加入语音、多真人联机、观战、复盘、排行榜和账号体系，无需推翻当前工程骨架。

## 二、技术栈详情（固定无歧义）

| 技术模块 | 具体选型 | 版本建议 | 核心作用 |
|---|---|---|---|
| Web 框架 | FastAPI | 0.115.x | REST 接口、依赖注入、OpenAPI 文档、WebSocket 支持 |
| ASGI 服务器 | Uvicorn | 0.30.x | 启动和承载后端服务 |
| 数据校验 | Pydantic | 2.8.x | 请求/响应模型定义与校验 |
| ORM | SQLAlchemy | 2.0.x | 数据持久化与查询抽象 |
| 迁移工具 | Alembic | 1.13.x | 数据库版本管理 |
| 缓存与会话 | Redis | 7.x | 房间状态缓存、连接状态、限流、消息缓冲 |
| 异步任务 | Celery 或 APScheduler | 按需 | AI 发言超时、回合结算、延迟消息调度 |
| 测试工具 | Pytest | 8.x | 单元测试与接口测试 |
| 代码规范 | Ruff + Black | Ruff 0.6.x、Black 24.x | 代码格式与静态检查 |

### 选型说明

FastAPI 适合快速构建结构清晰的异步服务，天然支持 REST 与 WebSocket；Pydantic v2 能保证消息结构统一；SQLAlchemy 与 Alembic 便于后续做持久化；Redis 适合承载对局态和临时状态。

## 三、整体架构设计（分层清晰）

### 3.1 分层架构

```plain text
后端架构（FastAPI + WebSocket）
├─ 接口层（API）：REST 与 WebSocket 入口，负责请求接入、参数校验、响应输出
├─ 应用层（Application）：对局编排、阶段推进、命令分发、事件聚合
├─ 领域层（Domain）：狼人杀规则、角色能力、投票逻辑、胜负判定
├─ 基础设施层（Infrastructure）：数据库、Redis、消息队列、外部 AI 调用、日志
└─ 实体与模型层（Models/Schemas）：数据库模型、Pydantic 模型、领域对象
```

### 3.2 推荐目录结构

```plain text
app/
├── api/
│   ├── routers/
│   │   ├── health.py
│   │   ├── games.py
│   │   └── rooms.py
│   └── websockets/
│       └── game_ws.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── logging.py
│   └── exceptions.py
├── domain/
│   ├── enums.py
│   ├── rules/
│   ├── services/
│   └── events/
├── schemas/
│   ├── game.py
│   ├── player.py
│   ├── vote.py
│   └── socket.py
├── models/
│   ├── base.py
│   ├── game.py
│   ├── player.py
│   └── action.py
├── services/
│   ├── game_service.py
│   ├── room_service.py
│   ├── ai_service.py
│   ├── vote_service.py
│   └── result_service.py
├── repositories/
│   ├── game_repo.py
│   ├── player_repo.py
│   └── action_repo.py
├── websocket/
│   ├── manager.py
│   └── broadcaster.py
├── utils/
│   ├── time.py
│   ├── ids.py
│   └── validate.py
├── tests/
└── main.py
```

## 四、核心业务边界

### 4.1 后端负责

- 创建和管理游戏房间
- 生成和维护玩家身份
- 推进昼夜与发言阶段
- 调度 AI 发言与 AI 行动
- 接收用户投票并计算结果
- 根据规则判定胜负
- 通过 WebSocket 推送实时事件

### 4.2 前端负责

- 展示房间状态和对局状态
- 提交发言与投票
- 显示系统公告和角色信息
- 根据后端消息更新 UI

## 五、核心数据模型

### 5.1 领域实体

- Game：一局游戏的核心元信息
- Room：房间信息与成员信息
- Player：玩家信息，包含真人或 AI 标识
- Role：身份信息，包含狼人、平民、预言家等
- Action：行动记录，包含发言、投票、技能使用
- GameEvent：对局事件，驱动实时消息推送

### 5.2 核心状态字段

- game_id
- room_id
- status
- phase
- current_round
- players
- alive_players
- dead_players
- votes
- chat_history
- announcements
- winner_faction

## 六、接口设计

### 6.1 REST 接口

| 接口 | 方法 | 用途 |
|---|---|---|
| `/api/health` | GET | 服务健康检查 |
| `/api/games` | POST | 创建游戏 |
| `/api/games/{game_id}` | GET | 获取游戏详情 |
| `/api/games/{game_id}/join` | POST | 加入游戏 |
| `/api/games/{game_id}/start` | POST | 开始游戏 |
| `/api/games/{game_id}/speak` | POST | 提交发言 |
| `/api/games/{game_id}/vote` | POST | 提交投票 |
| `/api/games/{game_id}/result` | GET | 获取结算结果 |
| `/api/games/{game_id}/replay` | GET | 获取复盘数据 |

### 6.2 WebSocket 接口

推荐连接地址：

- `ws://host/ws/game?gameId=xxx&playerId=yyy`

### 6.3 WebSocket 消息类型

| 类型 | 含义 |
|---|---|
| room_update | 房间状态变化 |
| game_status | 游戏阶段变化 |
| role_info | 身份下发 |
| announce | 系统公告 |
| ai_speak | AI 发言 |
| player_speak | 真人发言广播 |
| vote_result | 投票结果 |
| player_update | 玩家存活状态变化 |
| game_over | 游戏结束 |
| error | 异常信息 |

### 6.4 消息设计原则

- 消息结构必须稳定、可版本化
- 每个消息都应包含 type、timestamp、payload
- 复杂数据统一使用 Pydantic 模型序列化
- WebSocket 事件与领域事件保持一一对应

## 七、对局流程设计

### 7.1 创建房间

1. 用户通过前端请求创建游戏。
2. 后端生成 game_id、房间基础信息与首个玩家身份。
3. 后端返回房间状态，并建立后续推送上下文。

### 7.2 加入房间

1. 用户输入房间号。
2. 后端校验房间是否存在、是否允许加入。
3. 加入成功后返回玩家信息与当前房间状态。

### 7.3 开局流程

1. 达到最小人数后允许开局。
2. 后端分配身份并锁定房间状态。
3. 后端推送 role_info 与 game_status。
4. 进入夜晚阶段，开始第一轮行动。

### 7.4 白天与投票

1. 夜晚结束后进入白天公告。
2. 后端聚合夜间结果并广播。
3. 进入发言阶段，收集玩家和 AI 发言。
4. 发言结束后进入投票阶段。
5. 后端统计投票并执行淘汰。

### 7.5 胜负判定

1. 每轮投票后检查胜负条件。
2. 若满足胜利条件，进入 end 状态。
3. 推送 game_over 与 result 数据给前端。

## 八、AI 服务设计

### 8.1 AI 能力拆分

- 身份推理
- 夜间行动决策
- 白天发言生成
- 投票决策
- 复盘总结生成

### 8.2 AI 调用原则

- AI 调用不阻塞主流程
- AI 输出必须经过结构化校验
- AI 决策超时要有降级策略
- AI 结果应可落盘，便于调试与复盘

## 九、数据库与缓存设计

### 9.1 数据库存储建议

- game 表：游戏主记录
- room 表：房间主记录
- player 表：玩家主记录
- action 表：行动记录
- vote 表：投票记录
- result 表：结算记录

### 9.2 Redis 使用建议

- 房间在线成员缓存
- 对局阶段缓存
- WebSocket 连接映射
- 短时广播消息队列
- 限流与防重复提交标记

## 十、异常与安全策略

### 10.1 异常处理

- 参数校验失败直接返回统一错误结构
- 房间不存在、已结束、人数不足等场景返回明确错误码
- WebSocket 异常需要同步写日志并通知前端

### 10.2 安全策略

- 以房间和玩家上下文控制访问范围
- 严禁前端直接传递敏感身份信息作为最终依据
- 所有重要状态变更都必须由后端校验后写入
- 对投票、发言和加入房间做频率限制

## 十一、开发顺序建议

### 11.1 第一阶段：服务骨架

- 创建 FastAPI 工程
- 配置配置中心、日志和异常处理
- 打通健康检查接口
- 建立基础目录结构

### 11.2 第二阶段：房间与对局骨架

- 完成创建房间
- 完成加入房间
- 完成开始游戏
- 完成房间状态查询

### 11.3 第三阶段：WebSocket 实时层

- 完成连接管理
- 完成消息广播
- 完成阶段推送
- 完成身份下发

### 11.4 第四阶段：核心规则引擎

- 完成身份分配
- 完成夜间逻辑
- 完成发言与投票流程
- 完成胜负判定

### 11.5 第五阶段：AI 与复盘

- 完成 AI 发言与投票接口
- 完成结果汇总
- 完成复盘数据输出
- 完成测试与联调

## 十二、验收标准

以下条件满足即可视为后端 MVP 达标：

- 能创建和加入房间
- 能稳定提供 WebSocket 推送
- 能完成一局完整对战流程
- 能给前端提供身份、发言、投票和结算数据
- 能输出可复盘的结果记录

## 十三、文档交付建议

建议项目根目录最终保留以下文档：

- `后端README.md`：后端启动说明与入口
- `AI狼人杀（FastAPI+WebSocket）后端技术文档.md`：完整后端设计方案
- `后端开发任务清单.md`：后端执行任务列表
