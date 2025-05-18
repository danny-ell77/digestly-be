"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Optional
from enum import Enum


class Modes(str, Enum):
    TLDR = "tldr"
    KEY_INSIGHTS = "key_insights"
    COMPREHENSIVE = "comprehensive"
    CUSTOM = "custom"
    ARTICLE = "article"

    def __str__(self):
        return str(self.value)


class OutputMode(str, Enum):
    HTML = "html"
    MARKDOWN = "markdown"


class TranscriptRequest(BaseModel):
    video_id: str
    language_code: Optional[str] = None
    prompt_template: Optional[str] = None
    mode: Optional[Modes] = "comprehensive"  # Default to comprehensive mode
    # output_mode: Optional[OutputMode] = "html"


class ClaudePrompt(BaseModel):
    transcript: str
    prompt_template: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    system_prompt: Optional[str] = None


class TranscriptResponse(BaseModel):
    video_id: str
    transcript: str
    size: str
    claude_response: Optional[str] = None


class VideoProcessorResponse(BaseModel):
    video_id: str
    response: str


class VideoDataResponse(BaseModel):
    video_id: str
    title: str
    channel_title: str
    description: str
    thumbnail_url: str
    published_at: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str
