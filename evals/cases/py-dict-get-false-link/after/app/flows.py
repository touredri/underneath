from .cache import ReportCache

CACHE = ReportCache()


def available(flows, allowed):
    """Flows the role may open, in menu order."""
    result = []
    for name in flows:
        if allowed.get(name, False):
            result.append(name)
    return result


def cached_report(key):
    hit = CACHE.get(key)
    return hit if hit is not None else "missing"
