from app.services.game_service import record_vote


def submit_vote(game_id: str, target_id: str) -> None:
    record_vote(game_id, target_id)
