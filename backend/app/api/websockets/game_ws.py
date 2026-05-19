import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.socket import SocketMessage
from app.services.game_service import get_game
from app.utils.time import utc_now_iso
from app.websocket.broadcaster import manager

router = APIRouter()


@router.websocket("/ws/game")
async def game_ws(websocket: WebSocket) -> None:
    game_id = websocket.query_params.get("gameId", "")
    await manager.connect(game_id, websocket)
    try:
        snapshot = get_game(game_id)
        await websocket.send_text(
            SocketMessage(type="announce", timestamp=utc_now_iso(), payload={"content": f"进入房间 {snapshot.game_id}"}).model_dump_json()
        )
        while True:
            raw_message = await websocket.receive_text()
            try:
                parsed = json.loads(raw_message)
            except json.JSONDecodeError:
                await websocket.send_text(
                    SocketMessage(type="announce", timestamp=utc_now_iso(), payload={"content": "无效消息"}).model_dump_json()
                )
                continue
            await manager.broadcast(game_id, json.dumps(parsed, ensure_ascii=False))
    except WebSocketDisconnect:
        manager.disconnect(game_id, websocket)
