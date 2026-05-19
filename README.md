# AI狼人杀（Vue3全生态）前端项目

这是一个面向纯文字狼人杀玩法的前端项目，采用 Vue3 全生态方案实现。前端只负责页面展示、交互和状态管理，游戏规则、AI 决策和流程控制都由后端统一提供，前后端通过 REST 与 WebSocket 协作。

## 项目目标

先交付一个可玩的 MVP：1 名真人玩家与 4 到 5 名 AI 完成完整对局流程，包括创建/加入房间、身份分配、昼夜切换、文字发言、投票淘汰与胜负结算。后续再在不重构核心结构的前提下扩展语音、多真人联机和复盘能力。

## 主要技术栈

- Vue 3 + Vite
- TypeScript
- Pinia
- Vue Router
- Element Plus
- Axios
- WebSocket
- ESLint + Prettier

## 文档入口

- [项目构建总文档](项目构建总文档.md)
- [开发任务清单](开发任务清单.md)
- [原始技术方案](AI狼人杀（Vue3全生态）前端技术文档.md)

## 环境要求

- Node.js 20 或更高版本
- pnpm 9 或更高版本，推荐作为默认包管理器
- Python 3.11 或更高版本（后端）
- 可访问的后端服务，提供 REST 接口与 WebSocket 服务

## 快速开始

1. 进入 `frontend/` 安装依赖并启动前端。
2. 进入 `backend/` 安装依赖并启动后端。
3. 配置环境变量（参考各自目录下的 `.env.example`）。
4. 打开首页，创建房间或加入房间。

前端常用脚本：

- `pnpm dev`：启动开发环境
- `pnpm build`：生成生产构建
- `pnpm preview`：本地预览构建结果
- `pnpm lint`：代码检查

后端启动示例：

- `python -m pip install -r requirements.txt`
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## 项目结构

- `frontend/`：Vue 3 + Vite 前端工程
- `backend/`：FastAPI + WebSocket 后端工程

## 推荐目录约定

```plain text
src/
├── api/
├── hooks/
├── store/
├── components/
├── views/
├── router/
├── types/
├── utils/
├── assets/
├── App.vue
└── main.ts
```

## 约定的环境变量

- `VITE_API_BASE_URL`：REST 接口基础地址
- `VITE_WS_URL`：WebSocket 服务地址
- `VITE_APP_TITLE`：页面标题
- `VITE_ENABLE_MOCK`：是否启用本地模拟数据

## 开发原则

- 前后端彻底分离，前端不实现游戏裁决逻辑。
- 所有游戏状态进入 Pinia，避免组件之间手动传递深层数据。
- WebSocket 只负责实时事件，REST 负责资源创建与查询。
- 组件职责单一，页面负责编排，组件负责展示。
- 所有接口、消息和类型先定义，再实现页面。

## 交付标准

- 首页、房间页、对局页、结算页可完整流转。
- WebSocket 可稳定接收游戏状态、发言、投票和公告事件。
- 前端有明确的类型定义和状态管理结构。
- 文档、任务清单和项目结构能支持后续正式开发。

## 后续扩展方向

- 语音聊天与语音识别
- 多真人联机
- 对局复盘与历史记录
- 账号体系与战绩统计
- 移动端适配与原生客户端
