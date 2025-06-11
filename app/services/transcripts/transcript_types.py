from typing import Optional
from abc import ABC, abstractmethod


class BaseTranscriptProcessor(ABC):
    """Abstract base class for transcript processing"""

    @abstractmethod
    async def fetch_transcript(
        self, video_id: str, language_code: Optional[str] = None
    ) -> str:
        """
        Fetch transcript for a given video ID

        Args:
            video_id (str): The YouTube video ID
            language_code (Optional[str]): Preferred language code

        Returns:
            str: The transcript text

        Raises:
            ValueError: If transcript cannot be fetched
        """
        pass
