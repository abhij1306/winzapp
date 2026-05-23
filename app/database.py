from typing import NoReturn


async def get_db() -> NoReturn:
    raise RuntimeError("Database session is configured in S1-T02")
