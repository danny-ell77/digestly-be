from .transcript_types import BaseTranscriptProcessor
from typing import Optional, List
from app.logger import get_logger
from .implementations.ytdlp_processor import YTDLPProcessor
from .implementations.yungs_transcripts_api import YungTranscriptsProcessor

logger = get_logger("transcript")


class TranscriptProcessor(BaseTranscriptProcessor):
    """Main processor that tries multiple implementations in sequence"""

    def __init__(self):

        self.processors: List[BaseTranscriptProcessor] = [
            YungTranscriptsProcessor(),
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
