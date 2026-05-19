# AI狼人杀后端项目

这是 AI狼人杀 纯文字网页端的后端服务说明。后端以 FastAPI + WebSocket 为核心，负责游戏房间、对局流程、AI 决策、投票裁决和实时消息推送。

## 项目目标

提供一套稳定的对局服务，让前端能够创建房间、加入房间、接收身份信息、参与发言投票，并最终获得结算结果与复盘数据。

## 主要职责

- 维护游戏和房间状态
- 分配身份和推进阶段
- 接收发言和投票
- 组织 AI 决策与行动
- 通过 WebSocket 推送实时事件
- 输出结算和复盘结果

## 主要技术栈

- FastAPI
- Uvicorn
- Pydantic
- SQLAlchemy
- Alembic
- Redis
- Pytest
- Ruff + Black

## 文档入口

- [后端技术总文档](AI狼人杀（FastAPI+WebSocket）后端技术文档.md)
- [后端开发任务清单](后端开发任务清单.md)
- [前端项目 README](README.md)

## 推荐运行环境

- Python 3.11 或更高版本
- Redis 7.x
- PostgreSQL 16 或本地开发使用 SQLite

## 开发原则

- 规则与裁决都在后端
- 前后端消息结构保持稳定
- WebSocket 与 REST 职责分离
- 所有状态变更都可追踪
- 先定义模型，再实现逻辑

## 后续扩展

- 语音房间与语音识别
- 多真人联机
- 观战与回放
- 账号系统与战绩统计
