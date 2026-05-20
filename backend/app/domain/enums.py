from enum import Enum


class GameStatus(str, Enum):
    waiting = "waiting"
    role_select = "role_select"  # 抢身份阶段
    night = "night"
    day = "day"
    sheriff_election = "sheriff_election"  # 警长竞选阶段
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
    sheriff_elect_start = "sheriff_elect_start"   # 警长竞选开始
    sheriff_campaign = "sheriff_campaign"         # 玩家上警/退选
    sheriff_speech_turn = "sheriff_speech_turn"   # 警长竞选发言轮次
    sheriff_vote = "sheriff_vote"                 # 警长竞选投票
    sheriff_elect_result = "sheriff_elect_result" # 警长竞选结果
    sheriff_transfer = "sheriff_transfer"         # 警长转让徽章
    wolf_self_destruct = "wolf_self_destruct"     # 狼人自爆
    error = "error"                       # 错误消息
