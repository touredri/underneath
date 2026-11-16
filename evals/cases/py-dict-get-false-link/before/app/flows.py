from .cache import ReportCache

CACHE = ReportCache()


def available(flows):
    return list(flows)
