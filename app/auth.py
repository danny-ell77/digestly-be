from uuid import UUID
import os
from typing import Optional, Dict, Any, Annotated
import logging
from fastapi import Depends, Request, HTTPException
import jwt
from dotenv import load_dotenv
from app.constants import ANON_ID_FRAGMENT

load_dotenv()

logger = logging.getLogger("digestly")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://sdmcnnyuiyzmazdakglz.supabase.co")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

if not SUPABASE_JWT_SECRET:
    logger.warning("SUPABASE_JWT_SECRET not set in environment")

ValidateAnonId = UUID


def validate_jwt_token(token: str) -> Dict[str, Any]:
    """
    Validates a JWT token directly using the JWT secret

    Args:
        token: JWT token from client

    Returns:
        Dictionary with user information if token is valid

    Raises:
        HTTPException: If token is invalid or verification fails
    """
    if not SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",  # Supabase default audience
        )

        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "app_metadata": payload.get("app_metadata", {}),
            "user_metadata": payload.get("user_metadata", {}),
            "role": payload.get("role"),
            "aud": payload.get("aud"),
            "exp": payload.get("exp"),
            "iat": payload.get("iat"),
        }

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")


async def validate_token(token: str) -> Dict[str, Any]:
    """
    Validates a JWT token or anonymous ID

    Args:
        token: JWT token or anon ID from client

    Returns:
        Dictionary with user information if token is valid

    Raises:
        HTTPException: If token is invalid or verification fails
    """

    # Handle anonymous users
    if ANON_ID_FRAGMENT in token:
        try:
            anon_id = token.split(":")[1].strip()
            ValidateAnonId(anon_id)
            return {
                "id": anon_id,
                "email": None,
                "app_metadata": {},
                "user_metadata": {},
                "role": "anon",
            }
        except ValueError:
            logger.error("Invalid Anon ID format")
            raise HTTPException(status_code=400, detail="Invalid Anon ID format")

    if token.startswith("Bearer "):
        token = token[7:]
    return validate_jwt_token(token)


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
