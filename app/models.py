"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime


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
    tags: Optional[list[str]] = list()


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
