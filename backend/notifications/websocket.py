"""WebSocket manager для real-time уведомлений.

Пользователи подключаются через WS и получают обновления тикетов,
проектов и уведомлений без polling.
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Менеджер WS-подключений. Хранит активные соединения по user_id."""

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)
        logger.info("WS connected: user=%s (total=%d)", user_id[:8], self._total())

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info("WS disconnected: user=%s (total=%d)", user_id[:8], self._total())

    async def send_to_user(self, user_id: str, event: str, data: dict) -> None:
        """Отправить сообщение конкретному пользователю."""
        connections = self._connections.get(user_id, set())
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str)
        disconnected = set()
        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        for ws in disconnected:
            connections.discard(ws)

    async def broadcast_to_staff(self, event: str, data: dict) -> None:
        """Отправить всем подключённым staff-пользователям."""
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str)
        for user_id, connections in list(self._connections.items()):
            disconnected = set()
            for ws in connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.add(ws)
            for ws in disconnected:
                connections.discard(ws)

    def _total(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# Глобальный экземпляр
ws_manager = ConnectionManager()
