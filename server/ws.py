"""WebSocket broadcast hub for /ws/status.

Frames are plain JSON objects with a ``type`` field, one of
``status``, ``heard``, ``download``, ``log`` or ``update``.
The voice service pushes events from worker threads, so ``broadcast`` is
thread safe and hands the payload to the server event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.logging_setup import get_logger

log = get_logger("ws")

FRAME_TYPES = ("status", "heard", "download", "log", "update")
STATUS_INTERVAL_SECONDS = 2.0


class Hub:
    """Keeps the open panel sockets and fans events out to all of them."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ticker: asyncio.Task | None = None
        self._status_provider: Any | None = None

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._loop = loop or asyncio.get_event_loop()

    def set_status_provider(self, provider: Any) -> None:
        """``provider()`` returns the dict used for periodic status frames."""
        self._status_provider = provider

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        self._clients.add(websocket)
        log.info("Panel connected, %s client(s)", len(self._clients))
        if self._ticker is None or self._ticker.done():
            self._ticker = asyncio.create_task(self._status_loop())
        await self._send(websocket, self._status_frame())

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        log.info("Panel disconnected, %s client(s)", len(self._clients))
        if not self._clients and self._ticker is not None:
            self._ticker.cancel()
            self._ticker = None

    async def _send(self, websocket: WebSocket, frame: dict) -> bool:
        try:
            await websocket.send_json(frame)
            return True
        except Exception:
            return False

    async def broadcast_async(self, event: dict) -> None:
        frame = _normalise(event)
        if not self._clients:
            return
        dead = []
        for client in list(self._clients):
            if not await self._send(client, frame):
                dead.append(client)
        for client in dead:
            self._clients.discard(client)

    def broadcast(self, event: dict) -> None:
        """Thread safe entry point, used as the voice service event sink."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast_async(event), loop)
        except RuntimeError:
            log.debug("Broadcast dropped, event loop is not running")

    def _status_frame(self) -> dict:
        payload: dict = {}
        if self._status_provider is not None:
            try:
                payload = dict(self._status_provider() or {})
            except Exception as exc:
                payload = {"error": str(exc)}
        payload["type"] = "status"
        payload.setdefault("time", time.time())
        return payload

    async def _status_loop(self) -> None:
        try:
            while self._clients:
                await asyncio.sleep(STATUS_INTERVAL_SECONDS)
                if not self._clients:
                    break
                await self.broadcast_async(self._status_frame())
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Status loop stopped: %s", exc)

    async def shutdown(self) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ticker
            self._ticker = None
        for client in list(self._clients):
            with contextlib.suppress(Exception):
                await client.close()
        self._clients.clear()


def _normalise(event: dict) -> dict:
    frame = dict(event or {})
    kind = frame.get("type")
    if kind not in FRAME_TYPES:
        frame["type"] = "log" if kind is None else str(kind)
    return frame


hub = Hub()


def get_hub() -> Hub:
    return hub


async def status_endpoint(websocket: WebSocket) -> None:
    """Handler bound to /ws/status by the API module."""
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.disconnect(websocket)


def attach_service(service: Any) -> None:
    """Point the voice service event sink at this hub."""
    try:
        service.set_event_sink(hub.broadcast)
    except Exception as exc:
        log.warning("Could not attach event sink: %s", exc)
