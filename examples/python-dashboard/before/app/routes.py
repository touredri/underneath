from fastapi import APIRouter

from .db import get_session

router = APIRouter()


@router.get("/users/{user_id}")
async def get_user(user_id: int):
    async with get_session() as session:
        return await session.fetch("SELECT * FROM users WHERE id = $1", user_id)
