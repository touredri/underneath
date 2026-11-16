import functools
import time


def cached(ttl: float = 60.0):
    def decorator(fn):
        store = {}

        @functools.wraps(fn)
        async def wrapper(*args):
            now = time.monotonic()
            hit = store.get(args)
            if hit and now - hit[0] < ttl:
                return hit[1]
            value = await fn(*args)
            store[args] = (now, value)
            return value

        return wrapper

    return decorator
