"""
YouTube transcript/caption fetching functionality.
This module provides functions for fetching YouTube video transcripts,
utilizing both the YouTube Data API and the YouTube Transcript API.
"""

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from youtube_transcript_api.formatters import TextFormatter
import re
from app.logger import get_logger

# Get logger for this module
logger = get_logger("transcript")

# Constants
DEFAULT_LANGUAGE = "en"


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
    # Match YouTube URL patterns
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
        r"(?:shorts\/)([0-9A-Za-z_-]{11})",
        r"^([0-9A-Za-z_-]{11})$",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    raise ValueError("Could not extract YouTube video ID from provided URL or ID")


async def fetch_transcript_api(video_id: str, language_code: str = None) -> str:
    """
    Fetch transcript using YouTube Transcript API.

    Args:
        video_id (str): The YouTube video ID
        language_code (str, optional): Preferred language code. Defaults to None.

    Returns:
        str: Formatted transcript text

    Raises:
        HTTPException: If transcript cannot be fetched
    """
    import asyncio

    try:
        # Get video transcript - run in a thread pool as YouTubeTranscriptApi is synchronous
        languages = [language_code] if language_code else None
        loop = asyncio.get_event_loop()
        transcript_list = await loop.run_in_executor(
            None,
            lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=languages),
        )

        # Format transcript to plain text
        formatter = TextFormatter()
        transcript_text = formatter.format_transcript(transcript_list)
        logger.debug("Successfully retrieved transcript using YouTube Transcript API")

        return transcript_text

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.warning(f"YouTube Transcript API error: {str(e)}")
        raise ValueError(f"Transcript not found: {str(e)}")
    except Exception as e:
        logger.error(f"YouTube Transcript API unexpected error: {str(e)}")
        raise ValueError(f"Error retrieving transcript: {str(e)}")


async def get_transcript(video_id: str, language_code: str = None) -> str:
    """
    Get transcript using both APIs, with YouTube Data API as primary and Transcript API as fallback.

    Args:
        video_id (str): The YouTube video ID
        language_code (str, optional): Preferred language code. Defaults to None.

    Returns:
        str: The transcript text

    Raises:
        ValueError: If transcript cannot be fetched from either API
    """
    try:
        video_id = extract_video_id(video_id)
    except ValueError:
        # If it's not a URL, assume it's already a valid video ID
        pass

    language = language_code or DEFAULT_LANGUAGE

    # Try to get transcript from YouTube Data API first
    try:
        transcript_text = await fetch_transcript_api(video_id, language)
    except Exception as transcript_error:
        logger.error(f"YouTube Transcript API also failed: {str(transcript_error)}")
        raise ValueError(f"Failed to retrieve transcript: {str(transcript_error)}")

    if not transcript_text:
        logger.error("Failed to retrieve transcript from both APIs")
        raise ValueError("Failed to retrieve transcript from both APIs")

    return transcript_text
