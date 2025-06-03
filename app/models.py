"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime
from typing import TypedDict


class TimestampSegment(BaseModel):
    start: float
    duration: float
    text: str
    end: Optional[float] = None


class TranscriptWithTimestamps(BaseModel):
    video_id: str
    transcript_text: str
    segments: List[TimestampSegment]
    size: str


class DigestMode(str, Enum):
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
    mode: DigestMode
    # output_mode: Optional[OutputMode] = "html"
    tags: Optional[list[str]] = list()
    duration: int


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
    tags: Optional[list[str]] = []


class IdentityData(BaseModel):
    email: str
    email_verified: bool = False
    phone_verified: bool = False
    sub: str


class Identity(BaseModel):
    identity_id: str
    id: str
    user_id: str
    identity_data: IdentityData
    provider: str
    last_sign_in_at: datetime
    created_at: datetime
    updated_at: datetime
    email: str


class AppMetadata(BaseModel):
    provider: str
    providers: List[str]


class UserMetadata(BaseModel):
    email: str
    email_verified: bool = True
    phone_verified: bool = False
    sub: str


class SupabaseUser(BaseModel):
    id: str
    aud: str
    role: str
    email: str
    email_confirmed_at: Optional[datetime] = None
    phone: str = ""
    confirmed_at: Optional[datetime] = None
    last_sign_in_at: Optional[datetime] = None
    app_metadata: AppMetadata
    user_metadata: UserMetadata
    identities: List[Identity]
    created_at: datetime
    updated_at: datetime
    is_anonymous: bool = False

    class Config:
        from_attributes = True


class DigestlyVideoType(TypedDict):
    video_id: str
    title: str
    description: str
    channel_title: str
    tags: list[str]
    published_at: str
    thumbnail_url: str
    view_count: int
    like_count: int
    comment_count: int
    duration: str


def to_digestly_type(data: dict) -> DigestlyVideoType:
    """
    Transform YouTube API response data into Digestly video type format.
    Assumes data contains nested snippet, statistics, and contentDetails.

    Args:
        data: Complete YouTube video data with nested structures

    Returns:
        DigestlyVideoType: Formatted video data
    """
    snippet = data.get("snippet", {})
    statistics = data.get("statistics", {})
    content_details = data.get("contentDetails", {})

    return DigestlyVideoType(
        video_id=data.get("id", ""),
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        channel_title=snippet.get("channelTitle", ""),
        tags=snippet.get("tags", []),
        published_at=snippet.get("publishedAt", ""),
        thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
        view_count=int(statistics.get("viewCount", 0)),
        like_count=int(statistics.get("likeCount", 0)),
        comment_count=int(statistics.get("commentCount", 0)),
        duration=content_details.get("duration", ""),
    )
