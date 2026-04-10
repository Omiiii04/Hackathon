"""
backend/ws/manager.py
-----------------------
WebSocket connection manager + Redis pub/sub bridge.

How it works:
  1. Client opens WS /ws/{job_id}
  2. Manager listens on Redis channel ws:stage:{job_id}
  3. Celery worker publishes stage events via cache.redis_client.publish_stage()
  4. Manager forwards them to the connected WebSocket client
"""
import asyncio
import json
import logging
from typing import Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections keyed by job_id.
    Thread-safe for single-process deployments.
    """

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[job_id] = websocket
        logger.info(f"[WS] Client connected for job {job_id}")

    def disconnect(self, job_id: str):
        self._connections.pop(job_id, None)
        logger.info(f"[WS] Client disconnected for job {job_id}")

    async def send_json(self, job_id: str, data: dict):
        ws = self._connections.get(job_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.warning(f"[WS] Send failed for {job_id}: {e}")
                self.disconnect(job_id)

    async def broadcast_stage(
        self,
        job_id: str,
        stage: str,
        message: str,
        data: Optional[dict] = None,
        progress: int = 0,
    ):
        """Send a pipeline stage update to the connected client."""
        payload = {
            "type": "stage",
            "job_id": job_id,
            "stage": stage,
            "message": message,
            "progress": progress,
            "data": data or {},
        }
        await self.send_json(job_id, payload)

    async def send_result(self, job_id: str, result: dict):
        """Send the final verification result."""
        payload = {
            "type": "complete",
            "job_id": job_id,
            "stage": "complete",
            "result": result,
        }
        await self.send_json(job_id, payload)

    async def send_error(self, job_id: str, error: str):
        payload = {
            "type": "error",
            "job_id": job_id,
            "stage": "error",
            "error": error,
        }
        await self.send_json(job_id, payload)


# Module-level singleton
manager = ConnectionManager()


async def listen_for_job(job_id: str, websocket: WebSocket):
    """
    WebSocket endpoint handler.
    Subscribes to Redis pub/sub for job events and forwards them to the client.
    Also polls job status in case pub/sub messages were missed.
    """
    from cache.redis_client import subscribe_stages, get_job_status

    await manager.connect(job_id, websocket)

    try:
        # Check if job already finished before we connected
        existing = await get_job_status(job_id)
        if existing and existing.get("status") == "complete":
            await manager.send_result(job_id, existing.get("data", {}))
            return
        if existing and existing.get("status") == "failed":
            await manager.send_error(job_id, existing.get("data", {}).get("error", "Unknown error"))
            return

        # Subscribe to future events
        async for event in subscribe_stages(job_id):
            event_type = event.get("type", "stage")
            if event_type == "stage":
                await manager.broadcast_stage(
                    job_id,
                    stage=event.get("stage", ""),
                    message=event.get("message", ""),
                    data=event.get("data"),
                    progress=event.get("progress", 0),
                )
            elif event_type == "complete":
                await manager.send_result(job_id, event.get("result", {}))
                break
            elif event_type == "error":
                await manager.send_error(job_id, event.get("error", "Unknown error"))
                break

    except WebSocketDisconnect:
        logger.info(f"[WS] Client for {job_id} disconnected early")
    except Exception as e:
        logger.error(f"[WS] Error for {job_id}: {e}")
        await manager.send_error(job_id, str(e))
    finally:
        manager.disconnect(job_id)
