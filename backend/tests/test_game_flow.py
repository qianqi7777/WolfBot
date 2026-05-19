from fastapi.testclient import TestClient

from app.main import app


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
    assert started.json()["gameStatus"] == "speak"

    result = client.get(f"/api/games/{game_id}/result")
    assert result.status_code == 200
    assert result.json()["gameId"] == game_id
