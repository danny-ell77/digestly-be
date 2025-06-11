import os
import httpx
from typing import Optional
from app.logger import get_logger
from ..transcript_types import BaseTranscriptProcessor

logger = get_logger("transcript")


class YungTranscriptsProcessor(BaseTranscriptProcessor):
    def __init__(self):
        self.api_url = "https://www.youtubetranscripts.io/api/fetch-video"

        proxy_username = os.getenv("PROXY_USERNAME")
        proxy_password = os.getenv("PROXY_PASSWORD")

        if not (proxy_username and proxy_password):
            logger.error("Proxy credentials not set")
            raise ValueError("Invalid configuration")

        proxy_url = f"http://{proxy_username}:{proxy_password}@p.webshare.io:80"

        self.client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout
            proxies={"http://": proxy_url, "https://": proxy_url},
            verify=False,  # Disable SSL verification for testing
        )

    async def fetch_transcript(
        self, video_id: str, language_code: Optional[str] = None
    ) -> str:
        try:
            logger.info(f"Making request to {self.api_url} with video ID: {video_id}")
            response = await self.client.post(
                self.api_url,
                json={
                    "videoUrl": f"https://www.youtube.com/watch?v={video_id}",
                    "forceProxy": False,
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                },
            )

            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")

            # Log raw response for debugging
            raw_response = response.text
            logger.info(f"Raw response: {raw_response[:500]}...")  # Log first 500 chars

            if response.status_code != 200:
                raise ValueError(
                    f"API request failed with status {response.status_code}"
                )

            try:
                data = response.json()
            except Exception as json_error:
                logger.error(f"Failed to parse JSON response: {str(json_error)}")
                logger.error(f"Response content: {raw_response}")
                raise ValueError(f"Invalid JSON response: {str(json_error)}")

            if not data.get("success"):
                raise ValueError("API request was not successful")

            transcription_results = data.get("transcriptionResults", [])
            if not transcription_results:
                raise ValueError("No transcription results found")

            result = transcription_results[0]
            if not result.get("success") or not result.get("hasTranscript"):
                raise ValueError("No transcript available for this video")

            transcript_segments = result.get("transcript", [])
            if not transcript_segments:
                raise ValueError("No transcript segments found")

            # Format the transcript segments
            formatted_segments = []
            current_paragraph = []
            last_timestamp = None

            for segment in transcript_segments:
                text = segment.get("text", "").strip()
                offset = segment.get("offset", 0)

                if text:
                    current_paragraph.append(text)

                    is_sentence_end = text.endswith((".", "!", "?"))
                    time_gap = (
                        (offset - last_timestamp) > 30 if last_timestamp else True
                    )

                    if is_sentence_end or time_gap:
                        paragraph_text = " ".join(current_paragraph)
                        formatted_segments.append(f"{paragraph_text} [[{offset:.1f}]]")
                        current_paragraph = []
                        last_timestamp = offset

            if current_paragraph:
                paragraph_text = " ".join(current_paragraph)
                formatted_segments.append(paragraph_text)

            transcript_text = " ".join(formatted_segments)
            logger.debug(
                "Successfully retrieved transcript with timestamps using YoungTranscripts API"
            )
            return transcript_text

        except httpx.HTTPError as e:
            logger.error(f"YoungTranscripts API HTTP error: {str(e)}")
            raise ValueError(f"HTTP error retrieving transcript: {str(e)}")
        except Exception as e:
            logger.error(f"YoungTranscripts API error: {str(e)}")
            raise ValueError(f"Error retrieving transcript: {str(e)}")
