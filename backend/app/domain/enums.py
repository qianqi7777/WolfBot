from enum import Enum


class GameStatus(str, Enum):
    waiting = "waiting"
    night = "night"
    day = "day"
    speak = "speak"
    vote = "vote"
    end = "end"


class RoleType(str, Enum):
    wolf = "wolf"
    civilian = "civilian"
    prophet = "prophet"
    unknown = "unknown"


class MessageType(str, Enum):
    announce = "announce"
    ai_speak = "ai_speak"
    vote_result = "vote_result"
    game_status = "game_status"
    role_info = "role_info"
    player_update = "player_update"
    game_over = "game_over"
