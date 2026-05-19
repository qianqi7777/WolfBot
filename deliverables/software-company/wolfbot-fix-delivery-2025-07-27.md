# WolfBot 修复交付报告

## TL;DR

文档-vs-代码审查完成，共修复 22 个问题（16 个原始问题 + 6 个 QA Bug），后端测试通过，前端类型检查通过。

## 交付概览

| 项目 | 状态 |
|------|------|
| 交付状态 | ✅ 全部完成 |
| 后端测试 | 2/2 passed |
| 前端类型检查 | 0 errors |
| 已知遗留问题 | 无 |

## 修复清单

### 第一批：16 个原始问题（T01-T04）

| # | 类别 | 问题 | 修复 |
|---|------|------|------|
| 1 | 后端 | 缺少 night_action/night_result 消息类型 | enums.py 新增 |
| 2 | 后端 | 缺少 ai_speak_window_seconds 配置 | config.py 新增 |
| 3 | 后端 | NightActionRequest schema 缺失 | game.py 新增 |
| 4 | 后端 | Player 缺少 night_action_done 字段 | player.py 新增 |
| 5 | 后端 | get_game 无视角隔离 | game_service.py 加 requester_id 过滤 |
| 6 | 后端 | _assign_roles 非动态分配 | 改为 max(1, total//4) 狼人 |
| 7 | 后端 | start_game 初始状态非 night | 改为 GameStatus.night |
| 8 | 后端 | 缺少 record_night_action/resolve_night | game_service.py 新增 |
| 9 | 后端 | ai_service 游戏循环不完整 | 重写为 night→day→speak→vote |
| 10 | 后端 | record_vote 签名缺少 voter_id | 修复签名 |
| 11 | 后端 | start_room 未启动 AI 循环 | 调用 launch_ai_cycle |
| 12 | 后端 | 缺少夜间行动 API 端点 | games.py 新增 POST /action/night |
| 13 | 后端 | WebSocket 缺少夜间消息处理 | game_ws.py 新增 handler |
| 14 | 前端 | 缺少夜间行动类型定义 | game.ts 新增 |
| 15 | 前端 | gameStore 缺少夜间状态管理 | 新增 actions + state |
| 16 | 前端 | NightAction 组件缺失 | 新建组件 |

### 第二批：6 个 QA Bug（T05）

| # | 严重度 | 问题 | 修复文件 |
|---|--------|------|----------|
| Fix1 | HIGH | advance_round() 双重递增 | ai_service.py — 移除调用 |
| Fix2 | HIGH | night_result 载荷解析不匹配 | useGameSocket.ts — 从 checkedResults 提取 |
| Fix3 | HIGH | 投票可投自己 | game_service.py — voter_id==target_id 检查 |
| Fix4 | MEDIUM | NightAction 未排除自己 | NightAction.vue + GamePlay.vue |
| Fix5 | MEDIUM | GameRoom 未传 playerId | GameRoom.vue + gameApi.ts |
| Fix6 | LOW | 测试断言 gameStatus 过时 | test_game_flow.py |

## 修改文件清单

### 后端（12 文件）
- `app/domain/enums.py`
- `app/core/config.py`
- `app/schemas/game.py`
- `app/schemas/player.py`
- `app/services/game_service.py`
- `app/services/ai_service.py`
- `app/services/vote_service.py`
- `app/services/room_service.py`
- `app/api/routers/games.py`
- `app/api/routers/rooms.py`
- `app/api/websockets/game_ws.py`
- `tests/test_game_flow.py`

### 前端（13 文件）
- `src/types/game.ts`
- `src/store/modules/gameStore.ts`
- `src/api/gameApi.ts`
- `src/hooks/useGameSocket.ts`
- `src/hooks/useGameLogic.ts`
- `src/utils/validate.ts`
- `src/router/index.ts`
- `src/views/GamePlay.vue`
- `src/views/GameResult.vue`
- `src/views/GameRoom.vue`
- `src/components/common/ChatBox.vue`
- `src/components/common/VotePanel.vue`
- `src/components/common/NightAction.vue`（新建）

## 用户下一步建议

1. **启动项目联调**：`cd backend && uvicorn app.main:app --reload` + `cd frontend && npm run dev`，完整跑一遍游戏流程
2. **重点测试夜间行动**：狼人选目标→预言家查验→查看结果是否正确传递
3. **测试投票流程**：确认不能投自己、AI 投票屏蔽非己角色
4. **检查视角隔离**：用不同角色登录，确认看不到不该看的信息
5. **边界场景**：单狼人局、全平民局、AI 先死等极端情况
