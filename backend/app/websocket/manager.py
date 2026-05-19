from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.setdefault(game_id, []).append(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        items = self.connections.get(game_id, [])
        if websocket in items:
            items.remove(websocket)

    async def broadcast(self, game_id: str, message: str) -> None:
        for websocket in list(self.connections.get(game_id, [])):
            await websocket.send_text(message)

    async def send_to(self, websocket: WebSocket, message: str) -> None:
        await websocket.send_text(message)
