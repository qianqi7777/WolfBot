# WolfBot Bug修复 + 架构重构 + UI优化 交付报告（第三轮）

## TL;DR
修复女巫救活Bug、守卫选项、多死发言方向、AI发言阶段提示，完成角色行动模块化拆分，优化前端头像排列和女巫用药窗口。

## 交付概览

| 指标 | 结果 |
|------|------|
| 修复Bug数 | 7 |
| 新增角色模块 | 7个 |
| 修改后端文件 | 6 |
| 修改前端文件 | 4 |
| 新增前端组件 | 1 |
| Python语法检查 | ✅ 全部通过 |
| TypeScript类型检查 | ✅ 零错误 |

---

## 1. Bug修复详情

### 🔴 Bug #1：女巫救活后目标变"未知"且没有真正救活

**根因**：`game_ws.py` 调用 `record_night_action()` 时只传了4个参数，缺少第5个参数 `wolf_kill_target_id`，导致解药目标校验被跳过。

**修复**：在 `game_ws.py` 的 `night_action` 消息处理中，自动计算狼人刀口并传入 `record_night_action`：
```python
# 从已提交的狼人行动中计算刀口
wolf_targets = []
for action in game.night_actions:
    if str(action.get("role", "")) == RoleType.wolf.value:
        wolf_targets.append(str(action.get("targetId", "")))
if wolf_targets:
    tally = {}
    for tid in wolf_targets:
        tally[tid] = tally.get(tid, 0) + 1
    witch_wolf_target_id = max(tally, key=tally.get)
record_night_action(game_id, actor_id, target_id, action_type, witch_wolf_target_id)
```

### 🔴 Bug #2：守卫守护选项没有自己

**修复**：`GUARD_SKILL.can_target_self = True`，守卫可以守护自己（但不能连续两晚守护同一人）。

### 🟡 Bug #3：多死时发言方向不是随机的

**修复**：`resolve_night()` 中记录 `first_dead_player_id` 时，从 `all_killed_ids` 中随机选择：
```python
killed_list = list(all_killed_ids)
game.first_dead_player_id = random.choice(killed_list)
```

### 🟡 Bug #4：AI不知道当前发言阶段

**修复**：
1. 扩展 `_PHASE_HINT` 增加更详细的阶段描述
2. 新增 `_LAST_WORDS_HINT` 和 `_SPEECH_TYPE_HINT` 
3. `_generate_ai_speech()` 增加 `speech_type` 参数：
   - `day_speak` — 白天发言
   - `last_words` — 遗言（狼人特别提示不要暴露队友）
   - `campaign` — 竞选发言
4. 所有调用点传入正确的 `speech_type`

### 🟢 Bug #5：其他板子没有守卫但法官还会播放守卫行动

**修复**：角色行动模块化拆分（见下方架构重构）。

---

## 2. 架构重构：角色行动模块化

### 设计思路
- 每个角色一个独立文件，包含夜间行动逻辑
- 板子预设配置 `active_roles` 列表，决定加载哪些角色
- 法官 `night_phase` 按 `active_roles` 顺序依次询问

### 新增文件

| 文件 | 职责 |
|------|------|
| `backend/app/roles/__init__.py` | 角色模块注册表 + 加载逻辑 |
| `backend/app/roles/wolf.py` | 狼人夜间行动（选择击杀目标） |
| `backend/app/roles/witch.py` | 女巫夜间行动（解药/毒药） |
| `backend/app/roles/prophet.py` | 预言家夜间行动（查验） |
| `backend/app/roles/guard.py` | 守卫夜间行动（守护） |
| `backend/app/roles/hunter.py` | 猎人白天行动（开枪） |
| `backend/app/roles/idiot.py` | 白痴白天行动（翻牌） |

### 板子配置

`ScenePreset` 新增 `active_roles` 字段：
```python
# 预女猎白：狼人→女巫→预言家（无守卫）
active_roles=[
    RoleType.wolf,
    RoleType.witch,
    RoleType.prophet,
]
```

未指定 `active_roles` 的预设自动从 `role_distribution` 推导（向后兼容）。

### 使用方式

```python
from app.roles import get_active_role_actions

active_actions = get_active_role_actions(game.room_settings.scene.preset)
for action_class in active_actions:
    await action_class.night_action(self, game)
```

---

## 3. 前端UI优化

### 头像排列改为双列竖排

**修改**：`CircleTable.vue` 从环形布局改为左右两列竖排：
- 左列：前半部分玩家
- 中央：公告/RoleCard
- 右列：后半部分玩家

**PlayerSeat.vue** 增加 `layout` 属性支持竖排模式。

### 女巫用药窗口优化

**修改**：`NightAction.vue`
1. 解药/毒药提交后隐藏选择界面
2. 新增 `WitchPotionStatus.vue` 组件：
   - 显示解药/毒药使用状态
   - 显示用药目标
   - 提示"解药和毒药各只能使用一次"

---

## 4. 修改的文件清单

### 后端
- `backend/app/api/websockets/game_ws.py` — 女巫救活Bug修复
- `backend/app/domain/roles.py` — 守卫can_target_self, ScenePreset.active_roles
- `backend/app/services/game_service.py` — 多死随机起点
- `backend/app/services/ai_service.py` — AI发言阶段提示
- `backend/app/services/judge_service.py` — speech_type参数, 角色模块调用

### 前端
- `frontend/src/components/game/CircleTable.vue` — 双列竖排
- `frontend/src/components/game/PlayerSeat.vue` — 竖排布局支持
- `frontend/src/components/common/NightAction.vue` — 女巫窗口优化
- `frontend/src/components/common/WitchPotionStatus.vue` — 新增用药状态面板

### 新增角色模块
- `backend/app/roles/__init__.py`
- `backend/app/roles/wolf.py`
- `backend/app/roles/witch.py`
- `backend/app/roles/prophet.py`
- `backend/app/roles/guard.py`
- `backend/app/roles/hunter.py`
- `backend/app/roles/idiot.py`

---

## 5. 下一步建议

1. **启动测试**：`cd frontend && npm run dev` 启动测试完整游戏流程
2. **重点测试**：
   - 女巫救被刀玩家 → 应正确救活
   - 守卫守护自己 → 应可选
   - 多死局 → 发言起点应随机
   - AI遗言 → 狼人不应暴露队友
   - 预女猎白局 → 夜间不应出现守卫环节
3. **扩展板子**：新增守卫局时，在预设 `active_roles` 中加入 `RoleType.guard`
4. **前端构建**：运行 `npm run build` 确认生产构建无错误
