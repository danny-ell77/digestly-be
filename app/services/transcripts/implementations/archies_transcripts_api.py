import random
import httpx
from typing import Optional
from app.logger import get_logger
from ..transcript_types import BaseTranscriptProcessor
from app.settings import settings

logger = get_logger("transcript")


class ArchiesTranscriptsProcessor(BaseTranscriptProcessor):
    def __init__(self):
        self.api_url = settings.archies_transcripts_api_url

        proxy_url = f"http://{settings.proxy_username}:{settings.proxy_password}@p.webshare.io:80"

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
                    "User-Agent": self._generate_user_agent(),
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

    def _generate_user_agent(self):
        """Generate a realistic user agent string"""
        # Different Chrome versions
        chrome_versions = [
            "110.0.5481.177",
            "111.0.5563.64",
            "112.0.5615.49",
            "113.0.5672.63",
            "114.0.5735.90",
        ]

        # Different OS versions
        windows_versions = [
            "Windows NT 10.0; Win64; x64",
            "Windows NT 10.0; WOW64",
            "Windows NT 6.3; Win64; x64",
            "Windows NT 6.1; Win64; x64",
        ]

        chrome_version = random.choice(chrome_versions)
        windows_version = random.choice(windows_versions)

        return f"Mozilla/5.0 ({windows_version}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
