import asyncio


async def load_dashboard(user_id, filters=[]):
    orders, profile = await asyncio.gather(fetch_orders(user_id), fetch_profile(user_id))
    filters.append("recent")
    return {"orders": orders, "profile": profile, "filters": filters}


async def fetch_orders(user_id):
    await asyncio.sleep(0)
    return [{"id": 1, "user": user_id}]


async def fetch_profile(user_id):
    await asyncio.sleep(0)
    return {"id": user_id}
