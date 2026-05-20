from enum import Enum


class GameStatus(str, Enum):
    waiting = "waiting"
    role_select = "role_select"  # 抢身份阶段
    night = "night"
    day = "day"
    speak = "speak"
    vote = "vote"
    end = "end"


class RoleType(str, Enum):
    wolf = "wolf"
    civilian = "civilian"
    prophet = "prophet"
    guard = "guard"
    hunter = "hunter"
    witch = "witch"
    idiot = "idiot"       # 白痴
    unknown = "unknown"


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
    role_select_start = "role_select_start"     # 抢身份阶段开始
    role_select_choice = "role_select_choice"   # 玩家提交抢身份选择
    role_select_result = "role_select_result"   # 抢身份结果公布
    last_words = "last_words"             # 遗言
    error = "error"                       # 错误消息
