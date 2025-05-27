from fastapi import HTTPException
from app.auth import CurrentUser
from app.deps import logger
from app.db import supabase_client
from app.types import APIErrorCodes


async def check_credits(user: CurrentUser):

    profile = await supabase_client.get_profile(user["id"])

    if not profile:
        logger.error(f"User profile not found for ID: {user['id']}")
        raise HTTPException(
            status_code=404, detail=APIErrorCodes.USER_PROFILE_NOT_FOUND
        )

    credits = profile.get("credits", 0)

    # Check if user has enough credits
    if credits <= 0:
        logger.warning(f"User {user['id']} has insufficient credits: {credits}")
        raise HTTPException(status_code=403, detail=APIErrorCodes.INSUFFICIENT_CREDITS)


async def deduct_credit(user_id: str):
    """
    Deduct one credit from a user's account.
    This is a synchronous function to be used in streaming responses.
    """
    new_credit_balance = await supabase_client.deduct_credit(user_id)
    logger.info(
        f"Deducted credit from user {user_id}, new balance: {new_credit_balance}"
    )
    return new_credit_balance
