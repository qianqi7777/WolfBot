from fastapi.testclient import TestClient

from app.domain.enums import GameStatus, RoleType
from app.main import app
from app.services.game_service import get_game_state, record_night_action, resolve_night, start_game


def test_create_join_start_and_result() -> None:
    client = TestClient(app)

    created = client.post("/api/games", json={"playerName": "玩家A"})
    assert created.status_code == 200
    game = created.json()
    game_id = game["gameId"]

    joined = client.post(f"/api/games/{game_id}/join", json={"playerName": "玩家B"})
    assert joined.status_code == 200

    started = client.post(f"/api/games/{game_id}/start")
    assert started.status_code == 200
    assert started.json()["gameStatus"] == "night"

    result = client.get(f"/api/games/{game_id}/result")
    assert result.status_code == 200
    assert result.json()["gameId"] == game_id


def test_room_settings_update_and_capacity() -> None:
    client = TestClient(app)

    created = client.post("/api/games", json={"playerName": "玩家A"})
    assert created.status_code == 200
    game_id = created.json()["gameId"]

    updated = client.patch(
        f"/api/rooms/{game_id}/settings",
        json={
            "scene": {
                "preset": "six-player-dark",
                "name": "6人暗牌场",
                "description": "2狼4好人，神职为预言家和守卫，暗牌局，无警长，节奏快。",
                "playerCount": 6,
            },
            "ai": {
                "baseUrl": "https://example.com/v1",
                "apiKey": "secret-key",
                "model": "gpt-4o-mini",
                "timeoutSeconds": 15,
                "temperature": 0.5,
                "enableMock": False,
            },
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["roomSettings"]["scene"]["playerCount"] == 6
    assert payload["roomSettings"]["ai"]["hasApiKey"] is True

    for index in range(5):
        joined = client.post(f"/api/games/{game_id}/join", json={"playerName": f"玩家{index}"})
        assert joined.status_code == 200

    overflow = client.post(f"/api/games/{game_id}/join", json={"playerName": "玩家超额"})
    assert overflow.status_code == 409


def test_guard_blocks_wolf_attack() -> None:
    client = TestClient(app)

    created = client.post("/api/games", json={"playerName": "玩家A"})
    assert created.status_code == 200
    game_id = created.json()["gameId"]

    start_game(game_id)
    state = get_game_state(game_id)
    assert len(state.players) == 6

    guard = state.players[0]
    wolf = state.players[1]
    target = state.players[2]

    guard.role = RoleType.guard
    wolf.role = RoleType.wolf
    target.role = RoleType.civilian
    for player in state.players[3:]:
        player.role = RoleType.civilian

    state.game_status = GameStatus.night
    state.night_actions.clear()
    state.winner_faction = None

    record_night_action(game_id, guard.id, target.id)
    record_night_action(game_id, wolf.id, target.id)

    result = resolve_night(game_id)
    assert result["guard_blocked"] is True
    assert result["killed_player_id"] is None
    assert target.is_alive is True
