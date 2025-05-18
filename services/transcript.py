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
import googleapiclient.discovery
import html
import re
import os
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


async def fetch_youtube_captions(video_id: str, language_code: str = None) -> str:
    """
    Fetch captions from a YouTube video using the YouTube Data API.

    Args:
        video_id (str): The YouTube video ID
        language_code (str, optional): Preferred language code. Defaults to None.

    Returns:
        str: Formatted transcript text

    Raises:
        Exception: If captions cannot be fetched
    """
    logger.debug(f"Fetching captions for video_id: {video_id} using YouTube Data API")

    try:
        # Try to get API key from environment
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            logger.warning("YouTube API key not found, skipping YouTube Data API")
            raise ValueError("YouTube API key not set")

        # Create a YouTube API client
        youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

        # Get caption tracks for the video
        captions_response = (
            youtube.captions().list(part="snippet", videoId=video_id).execute()
        )  # Find the right caption track - prefer specified language or default to first available
        caption_id = None
        for item in captions_response.get("items", []):
            track_language = item["snippet"]["language"]
            is_auto = "auto" in item["snippet"]["trackKind"].lower()

            # If language code specified, look for matching language
            if language_code and track_language.startswith(language_code):
                caption_id = item["id"]
                logger.debug(f"Found matching language caption track: {track_language}")
                break
            # Otherwise prioritize non-auto-generated captions
            elif not is_auto and not caption_id:
                caption_id = item["id"]
                logger.debug(f"Found manual caption track: {track_language}")

        # If still no caption_id, take any available caption
        if not caption_id and captions_response.get("items"):
            caption_id = captions_response["items"][0]["id"]
            logger.debug("Using first available caption track")

        if not caption_id:
            logger.warning("No caption tracks found")
            raise ValueError("No caption tracks found")

        # Download the actual caption track
        caption_response = (
            youtube.captions().download(id=caption_id, tfmt="srt").execute()
        )  # Parse the caption content
        transcript_text = ""

        # The response is a byte-like object that needs to be processed
        # For SRT format, we need to parse it

        # For simplicity here, we'll use a simpler approach to extract text
        # You might want to use a proper SRT parser in production
        lines = caption_response.decode("utf-8").split("\n")
        for line in lines:
            # Skip empty lines, timecodes and numbers
            if line and not line.strip().isdigit() and "-->" not in line:
                # Remove HTML tags and entities
                clean_line = html.unescape(re.sub(r"<.*?>", "", line))
                if clean_line.strip():
                    transcript_text += clean_line.strip() + " "

        logger.debug("Successfully fetched captions from YouTube Data API")
        return transcript_text.strip()

    except Exception as e:
        logger.error(f"Error fetching captions from YouTube API: {str(e)}")
        # We'll let the caller handle the fallback
        raise


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
    try:
        # Get video transcript
        languages = [language_code] if language_code else None
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id,
            languages=languages,
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


def get_youtube_client():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("YouTube API key not found, skipping YouTube Data API")
        raise ValueError("YouTube API key not set")

    # Create a YouTube API client
    return googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
