from fastapi import APIRouter

from .db import get_session
from .services import load_dashboard

router = APIRouter()


@router.get("/users/{user_id}")
async def get_user(user_id: int):
    async with get_session() as session:
        return await session.fetch("SELECT * FROM users WHERE id = $1", user_id)


@router.get("/dashboard/{user_id}")
async def dashboard(user_id: int):
    return await load_dashboard(user_id)
