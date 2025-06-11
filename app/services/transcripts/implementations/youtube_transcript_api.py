import time
import os
from typing import Optional
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from youtube_transcript_api.proxies import WebshareProxyConfig
from app.logger import get_logger
from ..transcript_types import BaseTranscriptProcessor

logger = get_logger("transcript")


class YouTubeTranscriptAPIProcessor(BaseTranscriptProcessor):
    def __init__(self):
        self.proxy_username = os.getenv("PROXY_USERNAME")
        self.proxy_password = os.getenv("PROXY_PASSWORD")
        if not (self.proxy_username and self.proxy_password):
            logger.error("Proxy credentials not set")
            raise ValueError("Invalid configuration")

    def _retry_operation(self, func, max_retries: int = 4, delay: int = 5):
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if "no element found" in str(e) and attempt < max_retries - 1:
                    logger.error(
                        f"XML parse error on attempt {attempt + 1}, retrying in {delay}s..."
                    )
                    time.sleep(delay)
                    delay *= 2  # exponential backoff
                else:
                    raise ValueError("Unable to fetch transcript")

    async def fetch_transcript(
        self, video_id: str, language_code: Optional[str] = None
    ) -> str:
        try:
            languages = [language_code] if language_code else None

            def _inner_fetch():
                return YouTubeTranscriptApi(
                    proxy_config=WebshareProxyConfig(
                        proxy_username=self.proxy_username,
                        proxy_password=self.proxy_password,
                    )
                ).fetch(video_id, languages=languages)

            transcript_list = self._retry_operation(_inner_fetch)

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
                        formatted_segments.append(
                            f"{paragraph_text} [[{start_time:.1f}]]"
                        )
                        current_paragraph = []
                        last_timestamp = start_time

            if current_paragraph:
                paragraph_text = " ".join(current_paragraph)
                formatted_segments.append(paragraph_text)

            transcript_text = " ".join(formatted_segments)
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
