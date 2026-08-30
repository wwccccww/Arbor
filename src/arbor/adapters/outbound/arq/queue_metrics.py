from __future__ import annotations


def arq_import_queue_depth(redis_url: str | None, observability: object | None = None) -> int | None:
    if not redis_url:
        return None
    try:
        import redis

        from arbor.observability.redis import observed_redis

        client = redis.from_url(redis_url)
        with observed_redis(observability, "llen"):
            for key in ("arq:queue", "arq:queue:default"):
                depth = client.llen(key)
                if depth:
                    return int(depth)
            return int(client.llen("arq:queue"))
    except (OSError, ImportError):
        return None
