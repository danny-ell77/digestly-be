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
        logger.info(f"Starting usage tracking for function {func.__name__}")
        logger.debug(f"User ID: {user.get('id')}, Email: {user.get('email')}")

        try:
            logger.info("Checking user credits...")
            await check_credits(user)
            logger.info("Credit check passed")

            if asyncio.iscoroutinefunction(func):
                logger.debug("Executing async function")
                result = await func(*args, user=user, **kwargs)
            else:
                logger.debug("Executing sync function")
                result = func(*args, user=user, **kwargs)

            logger.info("Function execution completed successfully")

            logger.info("Deducting credit...")
            new_balance = await deduct_credit(user["id"])
            logger.info(f"Credit deducted. New balance: {new_balance}")

            return result

        except Exception as e:
            logger.error(f"Error in track_usage decorator: {str(e)}", exc_info=True)
            raise

    return wrapper
