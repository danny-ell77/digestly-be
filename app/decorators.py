from typing import Callable
import asyncio
import logging
from app.credits import deduct_credit, check_credits

from functools import wraps
from app.auth import CurrentUser

logger = logging.getLogger("digestly")


def track_usage(func: Callable):

    @wraps(func)
    async def wrapper(*args, user: CurrentUser, **kwargs):

        try:
            await check_credits(user)

            if asyncio.iscoroutinefunction(func):
                result = await func(*args, user=user, **kwargs)
            else:
                result = func(*args, user=user, **kwargs)

            await deduct_credit(user["id"])

            return result

        except Exception as e:
            logger.error(f"Error in track_usage decorator: {str(e)}", exc_info=True)
            raise

    return wrapper
