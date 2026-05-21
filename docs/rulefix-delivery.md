# WolfBot 规则修复 + AI决策增强 交付报告

## TL;DR
对照网易标准规则修复15个逻辑Bug，增强AI决策能力，涉及7个后端文件+5个前端文件。

## 交付概览

| 指标 | 结果 |
|------|------|
| 修复Bug数 | 15 |
| 修改后端文件 | 7 |
| 修改前端文件 | 5 |
| Python语法检查 | ✅ 全部通过 |
| TypeScript类型检查 | ✅ 零错误 |
| 跨文件一致性 | ✅ 全部通过 |

## 15个Bug修复详情

### 🔴 高优先级（核心规则）

| # | Bug | 修复方式 |
|---|-----|---------|
| 1 | 猎人最后神职不能开枪 | `_check_hunter_last_god()` 检查存活神职数，为0则禁止开枪 |
| 2 | 预言家不能连续验同一人 | `consecutive_target_allowed=False` + `last_prophet_target_id` 字段 + 校验逻辑 |
| 3 | 白天发言顺序完全不对 | 重写 `_alive_speak_order()`：有警长→警长定方向+最后发言；无警长→死左/死右；新增 `speak_direction_request` WebSocket消息 + 前端选方向UI |

### 🟡 中优先级

| # | Bug | 修复方式 |
|---|-----|---------|
| 4 | 竞选发言顺序应为上警逆序 | `list(reversed(game.sheriff_candidate_ids))` |
| 5 | 竞选发言中无法退水 | 广播 `canWithdraw` 字段 + SheriffElection.vue 退水按钮 |
| 6 | AI竞选发言用随机模板 | `_generate_ai_sheriff_speech()` 改调用AI API + 竞选专用prompt |
| 7 | AI投票看不到谁投了谁 | `_generate_ai_vote()` 注入投票状态+发言摘要 |

### 🟢 低优先级

| # | Bug | 修复方式 |
|---|-----|---------|
| 8 | 白痴文档"出局无遗言"描述有误 | 改为"翻牌免疫不出局，翻牌后不能投票" |
| 9 | 猎人开枪WebSocket缺胜负检查 | `game_ws.py` 增加 `_check_win_condition` 调用 |

### 🟢 AI信息增强

| # | Bug | 修复方式 |
|---|-----|---------|
| 10 | AI不知道白痴翻牌 | `_generate_ai_speech/vote()` 注入 `is_idiot_revealed` 信息 |
| 11 | AI不知道谁有警徽 | `_generate_ai_speech/vote()` 注入警长信息 |
| 12 | AI竞选发言没调API | 与 #6 合并处理 |

### 🟢 AI策略增强

| # | Bug | 修复方式 |
|---|-----|---------|
| 13 | AI预言家决策太随机 | `_get_suspicious_players()` 优先验可疑玩家（70%概率） |
| 14 | AI守卫决策太随机 | `_get_claimed_prophet()` 优先守警长（60%）/预言家（50%） |
| 15 | AI猎人开枪决策太随机 | `_ai_hunter_pick_target()` 优先射杀被怀疑玩家（60%） |

## 修改的文件清单

### 后端（7个文件）
- `backend/app/schemas/player.py` — 新增 last_prophet_target_id, is_idiot_revealed
- `backend/app/domain/roles.py` — PROPHET_SKILL consecutive_target_allowed=False, 全角色ai_hint增强
- `backend/app/domain/enums.py` — 新增 speak_direction_request, speak_direction 消息类型
- `backend/app/services/game_service.py` — GameState新字段, _alive_speak_order重写, 连验校验, 白痴翻牌标记
- `backend/app/services/judge_service.py` — _check_hunter_last_god, _ask_sheriff_direction, _ai_hunter_pick_target, 竞选修复
- `backend/app/services/ai_service.py` — AI上下文增强, 策略增强, 竞选prompt
- `backend/app/api/websockets/game_ws.py` — speak_direction处理, hunter_shoot胜负检查

### 前端（5个文件）
- `frontend/src/types/game.ts` — 新增类型定义
- `frontend/src/store/modules/gameStore.ts` — speakDirectionRequest状态
- `frontend/src/hooks/useGameSocket.ts` — speak_direction_request消息处理
- `frontend/src/views/GamePlay.vue` — 警长选发言方向UI
- `frontend/src/components/common/SheriffElection.vue` — 退水按钮

### 文档（1个文件）
- `mods/12人标准暗牌场(预女猎白).md` — 白痴翻牌描述修正

## 新增数据结构

### Player字段
- `last_prophet_target_id: str | None` — 预言家上次查验目标
- `is_idiot_revealed: bool` — 白痴是否已翻牌

### GameState字段
- `speak_direction: str | None` — 发言方向（left/right）
- `first_dead_player_id: str | None` — 昨夜死亡玩家ID

### WebSocket消息类型
- `speak_direction_request` — 服务端→前端，请求警长选方向
- `speak_direction` — 前端→服务端，警长提交方向选择

### 新增方法
- `judge_service._check_hunter_last_god()` — 检查猎人是否最后神职
- `judge_service._ask_sheriff_direction()` — 询问警长发言方向
- `judge_service._ai_hunter_pick_target()` — AI猎人开枪目标选择
- `ai_service._get_suspicious_players()` — 从聊天提取可疑玩家
- `ai_service._get_claimed_prophet()` — 从聊天提取自称预言家的玩家

## 下一步建议

1. **启动测试**：`cd frontend && npm run dev` 启动前端，创建12人房间验证完整游戏流程
2. **重点测试场景**：
   - 猎人被放逐且是最后神职→应不能开枪
   - 预言家连续两晚验同一人→应被拒绝
   - 有警长时白天→应弹出选方向UI
   - 竞选发言→应按上警逆序，发言时可退水
   - AI发言→应包含警长和白痴翻牌信息
3. **AI策略调优**：当前概率参数（70%/60%/50%）可根据实际表现调整
4. **守卫策略注意**：暗牌场守卫不知道谁是预言家，只能从聊天推断
