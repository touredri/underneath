import asyncio

from .cache import cached
from .db import get_session


async def fetch_orders(user_id: int):
    async with get_session() as session:
        return await session.fetch("SELECT * FROM orders WHERE user_id = $1", user_id)


async def fetch_profile(user_id: int):
    async with get_session() as session:
        return await session.fetch("SELECT * FROM profiles WHERE user_id = $1", user_id)


def summarize(orders, highlights=[]):
    for o in orders:
        if o["total"] > 100:
            highlights.append(o["id"])
    return {"count": len(orders), "big": highlights}


@cached(ttl=30)
async def load_dashboard(user_id: int):
    orders, profile = await asyncio.gather(fetch_orders(user_id), fetch_profile(user_id))
    return {"profile": profile, "orders": summarize(orders)}
