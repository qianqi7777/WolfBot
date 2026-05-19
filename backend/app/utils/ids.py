import secrets


def generate_game_id() -> str:
    return secrets.token_hex(3).upper()


def generate_player_id() -> str:
    return secrets.token_hex(4)
