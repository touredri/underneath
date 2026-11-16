from contextlib import asynccontextmanager


class Session:
    async def fetch(self, query: str, *params):
        ...

    async def close(self):
        ...


@asynccontextmanager
async def get_session():
    session = Session()
    try:
        yield session
    finally:
        await session.close()
