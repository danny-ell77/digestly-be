"""
Supabase database client.
"""

import os
import logging
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("digestly")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://sdmcnnyuiyzmazdakglz.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_SERVICE_ROLE_KEY:
    logger.warning("SUPABASE_SERVICE_ROLE_KEY not set in environment")


class SupabaseClient:
    """Client for interacting with Supabase database."""

    def __init__(self):
        self.url = SUPABASE_URL
        self.service_key = SUPABASE_SERVICE_ROLE_KEY
        self.headers = {
            "Apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def get_profile(self, user_id: str):
        """
        Get a user's profile from the profiles table.

        Args:
            user_id: The user's ID

        Returns:
            The user's profile data or None if not found
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.url}/rest/v1/profiles",
                    headers=self.headers,
                    params={
                        "or": f"(user_id.eq.{user_id},anon_user_id.eq.{user_id})",
                        "select": "*",
                    },
                )
                print(response.json(), response.status_code, "=" * 50)
                if response.status_code == 200 and response.json():
                    return response.json()[0]
                else:
                    logger.warning(f"Profile not found for user {user_id}")
                    return None
        except Exception as e:
            logger.exception(f"Error getting profile: {str(e)}")
            return None

    async def update_credits(self, user_id: str, credits: int):
        """
        Update a user's credits.

        Args:
            user_id: The user's ID
            credits: The new credit value

        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.url}/rest/v1/profiles",
                    headers=self.headers,
                    params={
                        "or": f"(user_id.eq.{user_id},anon_user_id.eq.{user_id})",
                        "select": "*",
                    },
                    json={"credits": credits},
                )

                if response.status_code in (200, 201, 204):
                    logger.info(f"Credits updated for user {user_id}: {credits}")
                    return True
                else:
                    logger.warning(
                        f"Failed to update credits for user {user_id}. "
                        f"Status: {response.status_code}, Response: {response.text}"
                    )
                    return False
        except Exception as e:
            logger.exception(f"Error updating credits: {str(e)}")
            return False

    async def deduct_credit(self, user_id: str):
        """
        Deduct one credit from a user's account.

        Args:
            user_id: The user's ID

        Returns:
            New credit balance if successful, None otherwise
        """
        try:
            profile = await self.get_profile(user_id)
            if not profile:
                logger.warning(
                    f"Cannot deduct credit: Profile not found for user {user_id}"
                )
                return None

            current_credits = profile.get("credits", 0)

            if current_credits <= 0:
                logger.warning(
                    f"User {user_id} has insufficient credits ({current_credits})"
                )
                return 0

            new_credits = current_credits - 1
            success = await self.update_credits(user_id, new_credits)

            if success:
                return new_credits
            return None
        except Exception as e:
            logger.exception(f"Error deducting credit: {str(e)}")
            return None

    async def create_anonymous_profile(self, data: dict):
        """
        Create an anonymous user profile with initial credits.

        Args:
            data: Additional data for the anonymous profile

        Returns:
            The created anonymous profile data
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/rest/v1/profiles",
                    headers=self.headers,
                    json={
                        "timezone": data.get("timezone", "UTC"),
                    },
                )

                if response.status_code in (200, 201):
                    return response.json()[0]
                else:
                    logger.error(f"Failed to create anonymous profile: {response.text}")
                    return None
        except Exception as e:
            logger.exception(f"Error creating anonymous profile: {str(e)}")
            return None


supabase_client = SupabaseClient()
