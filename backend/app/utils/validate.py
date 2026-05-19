def validate_player_name(value: str) -> bool:
    return bool(value.strip()) and len(value.strip()) <= 30
