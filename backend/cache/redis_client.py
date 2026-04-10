"""
backend/cache/redis_client.py
-------------------------------
Redis async client for result caching and WebSocket pub/sub.

Cache key schema:  claim:{md5(claim_text)}
TTL:               7 days (604800 seconds)
"""
import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from config import settings

logger = logging.getLogger(__name__)

# ── Singleton Redis pool ──────────────────────────────────────────────────────
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Returns (or creates) the shared async Redis connection pool."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Cache key helpers ─────────────────────────────────────────────────────────

def _cache_key(claim: str) -> str:
    digest = hashlib.md5(claim.strip().lower().encode()).hexdigest()
    return f"claim:{digest}"


def _job_key(job_id: str) -> str:
    return f"job:{job_id}"


def _stage_channel(job_id: str) -> str:
    return f"ws:stage:{job_id}"


# ── Result caching ────────────────────────────────────────────────────────────

async def get_cached_result(claim: str) -> Optional[dict]:
    """
    Retrieve a cached verification result.
    Returns None if not cached, Redis is unavailable, or offline mode is active
    and the claim has never been cached.
    """
    try:
        r = await get_redis()
        key = _cache_key(claim)
        raw = await r.get(key)
        if raw:
            logger.info(f"[Cache] HIT for '{claim[:40]}'")
            return json.loads(raw)
        logger.debug(f"[Cache] MISS for '{claim[:40]}'")
        return None
    except Exception as e:
        logger.warning(f"[Cache] get error: {e}")
        return None


async def cache_result(claim: str, result: dict, ttl_days: int = None) -> bool:
    """Store a verification result in Redis. Returns True on success."""
    if ttl_days is None:
        ttl_days = settings.cache_ttl_days
    try:
        r = await get_redis()
        key = _cache_key(claim)
        ttl_seconds = ttl_days * 86400
        await r.setex(key, ttl_seconds, json.dumps(result, default=str))
        logger.info(f"[Cache] Stored '{claim[:40]}' (TTL {ttl_days}d)")
        return True
    except Exception as e:
        logger.warning(f"[Cache] store error: {e}")
        return False


# ── Job state management ──────────────────────────────────────────────────────

async def set_job_status(job_id: str, status: str, data: dict = None, ttl: int = 3600):
    """Store job status in Redis (1h TTL by default)."""
    try:
        r = await get_redis()
        payload = {"status": status, "data": data or {}}
        await r.setex(_job_key(job_id), ttl, json.dumps(payload, default=str))
    except Exception as e:
        logger.warning(f"[Cache] job status error: {e}")


async def get_job_status(job_id: str) -> Optional[dict]:
    """Retrieve job status from Redis."""
    try:
        r = await get_redis()
        raw = await r.get(_job_key(job_id))
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"[Cache] get job error: {e}")
        return None


# ── WebSocket pub/sub ─────────────────────────────────────────────────────────

async def publish_stage(job_id: str, message: dict):
    """Publish a pipeline stage event so WebSocket handlers can forward it."""
    try:
        r = await get_redis()
        channel = _stage_channel(job_id)
        await r.publish(channel, json.dumps(message, default=str))
    except Exception as e:
        logger.warning(f"[Cache] publish error: {e}")


async def subscribe_stages(job_id: str):
    """Return an async generator yielding stage messages for a job."""
    try:
        r = await get_redis()
        pubsub = r.pubsub()
        channel = _stage_channel(job_id)
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    yield json.loads(message["data"])
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"[Cache] subscribe error: {e}")


# ── Utility ───────────────────────────────────────────────────────────────────

async def redis_ping() -> bool:
    """Returns True if Redis is reachable."""
    try:
        r = await get_redis()
        return await r.ping()
    except Exception:
        return False
