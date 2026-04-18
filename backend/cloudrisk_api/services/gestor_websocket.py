"""WebSocket connection manager for real-time game events."""

from __future__ import annotations

from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        # Maps user_id → clan_id so we can broadcast to a whole clan
        self._user_clan: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        self._user_clan.pop(user_id, None)

    def register_user_clan(self, user_id: str, clan_id: str) -> None:
        """Called when the client sends a register_clan event."""
        if clan_id:
            self._user_clan[user_id] = clan_id
        else:
            self._user_clan.pop(user_id, None)

    async def _try_send(self, user_id: str, message: dict) -> bool:
        """Envía `message` al WS de `user_id`. Si falla, lo desconecta y
        devuelve `False`. Si el usuario no está conectado, también `False`.
        Devuelve `True` sólo cuando el envío fue exitoso. Centraliza el
        "send + cleanup-on-failure" para los 3 métodos públicos.
        """
        ws = self.active_connections.get(user_id)
        if not ws:
            return False
        try:
            await ws.send_json(message)
            return True
        except Exception:
            self.disconnect(user_id)
            return False

    async def send_personal_message(self, message: dict, user_id: str):
        await self._try_send(user_id, message)

    async def broadcast(self, message: dict):
        # snapshot de IDs porque `_try_send` puede mutar `active_connections`
        # vía `disconnect()` y rompería el iterador.
        for user_id in list(self.active_connections.keys()):
            await self._try_send(user_id, message)

    async def broadcast_to_clan(self, clan_id: str, message: dict) -> int:
        """Send message to all connected members of a clan. Returns count sent."""
        members = [uid for uid, cid in self._user_clan.items() if cid == clan_id]
        sent = 0
        for user_id in members:
            if await self._try_send(user_id, message):
                sent += 1
        return sent
