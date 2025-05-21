"""
Supabase client for authentication validation.
"""

import os
from typing import Optional, Dict, Any, Annotated
import logging
from fastapi import Depends
import httpx
from dotenv import load_dotenv
from fastapi import Request, HTTPException

# Load environment variables
load_dotenv()

logger = logging.getLogger("digestly")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://sdmcnnyuiyzmazdakglz.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_SERVICE_KEY:
    logger.warning("SUPABASE_SERVICE_KEY not set in environment")


async def validate_token(token: str) -> Dict[str, Any]:
    """
    Validates a JWT token from Supabase Auth

    Args:
        token: JWT token from client

    Returns:
        Dictionary with user information if token is valid

    Raises:
        HTTPException: If token is invalid or verification fails
    """
    if not SUPABASE_SERVICE_KEY:
        raise HTTPException(
            status_code=500, detail="Supabase service key not configured"
        )

    # Remove Bearer prefix if present
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": SUPABASE_SERVICE_KEY,
                },
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"Token validation failed with status {response.status_code}: {response.text}"
                )
                raise HTTPException(
                    status_code=401, detail="Invalid authentication token"
                )
    except Exception as e:
        logger.exception("Error validating token")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


async def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user from request

    Args:
        request: FastAPI request object

    Returns:
        User data if authenticated

    Raises:
        HTTPException: If authentication fails
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    try:
        user = await validate_token(auth_header)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error authenticating user")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


# Optional version that doesn't require authentication in development
async def get_optional_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Dependency to get current user if authenticated, but doesn't require auth

    Args:
        request: FastAPI request object

    Returns:
        User data if authenticated, None otherwise
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return None

    try:
        user = await validate_token(auth_header)
        return user
    except Exception as e:
        logger.warning(f"Failed to validate optional user: {e}")
        return None


CurrentUser = Annotated[dict, Depends(get_current_user)]

OptionalUser = Annotated[Optional[dict], Depends(get_optional_user)]
