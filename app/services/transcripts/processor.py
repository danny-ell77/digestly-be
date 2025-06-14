import json
from .transcript_types import BaseTranscriptProcessor
from typing import Optional, List
from app.logger import get_logger
from app.db import supabase_client
from .implementations.ytdlp_processor import YTDLPProcessor
from .implementations.archies_transcripts_api import ArchiesTranscriptsProcessor
from .implementations.youtube_transcript_api import YouTubeTranscriptApi

logger = get_logger("transcript")


class SupabaseTranscriptProcessor(BaseTranscriptProcessor):

    async def fetch_transcript(self, video_id, language_code=None):
        """Fetch transcript from Supabase"""
        transcript = await supabase_client.get_transcript(video_id, language_code)
        if not transcript:
            raise ValueError(f"No transcript found for video ID: {video_id}")
        current_paragraph = []
        last_timestamp = None
        formatted_segments = []
        transcript_segments = json.loads(transcript)
        for segment in transcript_segments:
            text = segment.get("text", "").strip()
            start = segment.get("start", 0)

            if text:
                current_paragraph.append(text)

                is_sentence_end = text.endswith((".", "!", "?"))
                time_gap = (start - last_timestamp) > 30 if last_timestamp else True

                if is_sentence_end or time_gap:
                    paragraph_text = " ".join(current_paragraph)
                    formatted_segments.append(f"{paragraph_text} [[{start:.1f}]]")
                    current_paragraph = []
                    last_timestamp = start

        if current_paragraph:
            paragraph_text = " ".join(current_paragraph)
            formatted_segments.append(paragraph_text)

        transcript_text = " ".join(formatted_segments)
        return transcript_text


class TranscriptProcessor(BaseTranscriptProcessor):
    """Main processor that tries multiple implementations in sequence"""

    def __init__(self):

        self.processors: List[BaseTranscriptProcessor] = [
            SupabaseTranscriptProcessor(),  # This serves as a caching layer
            ArchiesTranscriptsProcessor(),
            YouTubeTranscriptApi(),
            YTDLPProcessor(),
        ]

    async def fetch_transcript(
        self, video_id: str, language_code: Optional[str] = None
    ) -> str:
        last_error = None

        for processor in self.processors:
            try:
                return await processor.fetch_transcript(video_id, language_code)
            except Exception as e:
                last_error = e
                logger.warning(f"{processor.__class__.__name__} failed: {str(e)}")
                continue

        if last_error:
            logger.error("All transcript fetching methods failed")
            raise ValueError(
                f"All transcript fetching methods failed: {str(last_error)}"
            )
        else:
            raise ValueError("No transcript processors available")
