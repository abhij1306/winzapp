from typing import NoReturn


async def get_redis() -> NoReturn:
    raise RuntimeError("Redis dependency is configured in S1-T07")
