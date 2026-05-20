from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, list[WebSocket]] = {}
        self.player_map: dict[str, dict[str, WebSocket]] = {}  # game_id -> {player_id: websocket}

    async def connect(self, game_id: str, websocket: WebSocket, player_id: str = "") -> None:
        await websocket.accept()
        self.connections.setdefault(game_id, []).append(websocket)
        if player_id:
            self.player_map.setdefault(game_id, {})[player_id] = websocket

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        items = self.connections.get(game_id, [])
        if websocket in items:
            items.remove(websocket)
        # 清理 player_map 中对应的映射
        player_map = self.player_map.get(game_id, {})
        to_remove = [pid for pid, ws in player_map.items() if ws is websocket]
        for pid in to_remove:
            del player_map[pid]

    async def broadcast(self, game_id: str, message: str) -> None:
        for websocket in list(self.connections.get(game_id, [])):
            await websocket.send_text(message)

    async def send_to(self, websocket: WebSocket, message: str) -> None:
        await websocket.send_text(message)

    @property
    def active_connections(self) -> dict[str, list[WebSocket]]:
        """兼容旧代码对 active_connections 的引用"""
        return self.connections

    async def send_to_player(self, game_id: str, player_id: str, message: str) -> bool:
        """向指定玩家发送消息。返回是否成功发送。"""
        ws = self.player_map.get(game_id, {}).get(player_id)
        if ws:
            await ws.send_text(message)
            return True
        return False
