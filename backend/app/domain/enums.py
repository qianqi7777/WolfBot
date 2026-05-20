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
    guard = "guard"
    hunter = "hunter"
    witch = "witch"
    unknown = "unknown"


class MessageType(str, Enum):
    room_update = "room_update"
    announce = "announce"
    ai_speak = "ai_speak"
    player_speak = "player_speak"
    speak_turn = "speak_turn"
    vote_result = "vote_result"
    vote_summary = "vote_summary"
    game_status = "game_status"
    role_info = "role_info"
    player_update = "player_update"
    game_over = "game_over"
    night_action = "night_action"
    night_result = "night_result"
    error = "error"
