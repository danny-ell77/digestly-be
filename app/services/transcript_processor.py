import os
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from youtube_transcript_api.proxies import WebshareProxyConfig
import re
from app.logger import get_logger

logger = get_logger("transcript")

DEFAULT_LANGUAGE = "en"


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL"""
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
        str: Formatted transcript text with timestamp links

    Raises:
        HTTPException: If transcript cannot be fetched
    """
    import asyncio

    try:
        languages = [language_code] if language_code else None
        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")
        if proxy_username and proxy_password:
            ytt_api = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=proxy_username,
                    proxy_password=proxy_password,
                )
            )
        else:
            ytt_api = YouTubeTranscriptApi()
        loop = asyncio.get_event_loop()
        transcript_list = await loop.run_in_executor(
            None,
            lambda: ytt_api.fetch(video_id, languages=languages),
        )

        formatted_segments = []
        current_paragraph = []
        last_timestamp = None

        for i, segment in enumerate(transcript_list):
            start_time = segment.start or 0
            text = str(segment.text).strip()

            if text:
                current_paragraph.append(text)

                is_sentence_end = text.endswith((".", "!", "?"))
                time_gap = (
                    (start_time - last_timestamp) > 30 if last_timestamp else True
                )
                is_last_segment = i == len(transcript_list) - 1

                if is_sentence_end or time_gap or is_last_segment:
                    paragraph_text = " ".join(current_paragraph)
                    formatted_segments.append(f"{paragraph_text} [[{start_time:.1f}]]")
                    current_paragraph = []
                    last_timestamp = start_time

        if current_paragraph:
            paragraph_text = " ".join(current_paragraph)
            formatted_segments.append(paragraph_text)

        transcript_text = " ".join(formatted_segments)
        with open("transcript.txt", "w") as f:
            f.write(transcript_text)
        logger.debug(
            "Successfully retrieved transcript with timestamps using YouTube Transcript API"
        )

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
        pass

    language = language_code or DEFAULT_LANGUAGE

    try:
        transcript_text = await fetch_transcript_api(video_id, language)
    except Exception as transcript_error:
        logger.error(f"YouTube Transcript API also failed: {str(transcript_error)}")
        raise ValueError(f"Failed to retrieve transcript: {str(transcript_error)}")

    if not transcript_text:
        logger.error("Failed to retrieve transcript from both APIs")
        raise ValueError("Failed to retrieve transcript from both APIs")

    return transcript_text
