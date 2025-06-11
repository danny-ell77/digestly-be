import os
import logging
import functools
from typing import AsyncGenerator
from app.decorators import track_usage
from app.model_selector import ModelSelector
from app.auth import CurrentUser
from app.models import (
    TranscriptRequest,
    TranscriptResponse,
    VideoDataResponse,
    to_digestly_type,
)

from app.db import supabase_client
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.services.content_processor import VideoProcessor
from app.services.transcripts.processor import TranscriptProcessor
from app.deps import (
    YoutubeClient,
    GroqClient,
)

load_dotenv()
logger = logging.getLogger("digestly")

app = FastAPI(
    title="YouTube Video Processor",
    description="API for processing YouTube videos with LLMs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # Cache preflight requests for 24 hours
)


def extract_video_id(video_id: str) -> str:
    """Extract video ID from YouTube URL or ID"""
    import re

    patterns = [
        r"^(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]

    for pattern in patterns:
        if match := re.search(pattern, video_id):
            return match.group(1)

    raise ValueError(f"Invalid YouTube video ID or URL: {video_id}")


@app.get("/")
async def root():
    return {"message": "YouTube Video Processor API is running"}


@app.post("/transcript/", response_model=TranscriptResponse)
async def get_transcript_endpoint(request: TranscriptRequest):
    """Get transcript from YouTube video ID"""
    try:
        video_id = request.video_id
        transcript_processor = TranscriptProcessor()
        transcript_text = await transcript_processor.fetch_transcript(
            video_id, request.language_code
        )

        return {
            "video_id": video_id,
            "transcript": transcript_text,
            "size": f"{len(transcript_text.split())} words, {len(transcript_text)} characters",
            "claude_response": None,  # Not processing with Claude yet
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {str(e)}")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving transcript: {str(e)}"
        )


@app.post("/process/")
@track_usage
async def process_transcript_endpoint(
    request: TranscriptRequest,
    user: CurrentUser,
    groq_client: GroqClient,
):
    """Get transcript and process it with LLM"""
    logger.info(
        f"Starting process_transcript function with video_id: {request.video_id}"
    )
    video_id = request.video_id
    model_config = ModelSelector().get_model_config(
        request.mode, request.duration // 60
    )
    llm_client = functools.partial(
        groq_client, model_config.primary_model, model_config.temperature
    )
    transcript_processor = TranscriptProcessor()
    processor = VideoProcessor(llm_client)

    try:
        transcript_text = await transcript_processor.fetch_transcript(
            video_id, request.language_code
        )

        # Check if video is longer than 45 minutes (2700 seconds) and save transcript
        # if request.duration > 2700:  # 45 minutes in seconds
        #     logger.info(
        #         f"Video {video_id} is longer than 45 minutes ({request.duration/60:.1f} mins), saving transcript"
        #     )
        await supabase_client.save_transcript(video_id, transcript_text)

        completion = await processor.process(
            transcript_text=transcript_text,
            mode=request.mode,
            custom_prompt=request.prompt_template,
            stream=False,
            tags=request.tags,
            duration=request.duration,
            max_tokens=model_config.max_tokens,
        )
        return {
            "video_id": video_id,
            "response": completion,
        }
    except ValueError as e:
        logger.error(f"Transcript not found error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in process_transcript: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing transcript: {str(e)}"
        )


@app.post("/process/stream/")
@track_usage
async def process_transcript_endpoint_stream(
    groq_client: GroqClient,
    user: CurrentUser,
    request: TranscriptRequest = Body(...),
):
    logger.info(
        f"Starting process_transcript function with video_id: {request.video_id}"
    )

    try:
        video_id = request.video_id
        mode = request.mode.value if request.mode else "comprehensive"

        model_config = ModelSelector().get_model_config(
            request.mode, request.duration // 60
        )
        llm_client = functools.partial(
            groq_client, model_config.primary_model, model_config.temperature
        )

        transcript_processor = TranscriptProcessor()
        processor = VideoProcessor(llm_client)
        # transcript_text = await process_youtube_video(video_id)
        transcript_text = await transcript_processor.fetch_transcript(
            video_id, request.language_code
        )

        if request.duration > 2700:  # 45 minutes in seconds
            logger.info(
                f"Video {video_id} is longer than 45 minutes ({request.duration/60:.1f} mins), saving transcript"
            )
            await supabase_client.save_transcript(video_id, transcript_text)

        completion: AsyncGenerator[str, None] = await processor.process(
            transcript_text=transcript_text,
            mode=mode,
            custom_prompt=request.prompt_template,
            tags=request.tags,
            stream=True,
            max_tokens=model_config.max_tokens,
        )

        async def stream_generator_wrapper(generator):
            async for chunk in generator:
                yield chunk

        return StreamingResponse(stream_generator_wrapper(completion))

    except ValueError as e:
        logger.error(f"Transcript not found error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in process_transcript: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing transcript: {str(e)}"
        )


@app.get("/video-data/", response_model=VideoDataResponse)
async def fetch_video_metadata(
    video_id: str,
    client: YoutubeClient,
):
    """Fetch metadata for a YouTube video"""
    logger.info(f"Fetching video metadata for video_id: {video_id}")
    try:
        try:
            video_id = extract_video_id(video_id)
        except (ValueError, NameError):
            pass

        video_data = (
            client.videos()
            .list(part="snippet,contentDetails,statistics", id=video_id)
            .execute()
        )

        # FOR DEBUGGING PURPOSES
        # with open("video_data.json", "w") as f:
        #     import json

        #     json.dump(video_data, f, indent=4)

        if not video_data.get("items"):
            logger.warning(f"No video found with ID: {video_id}")
            raise ValueError(f"No video found with ID: {video_id}")

        return to_digestly_type(video_data["items"][0])
    except ValueError as e:
        logger.error(f"Video not found error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching video metadata: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching video metadata: {str(e)}"
        )


@app.get("/user/profile/")
async def get_user_profile(user: CurrentUser):
    """Get authenticated user profile - requires valid authentication"""
    # Create Supabase client to get updated profile info
    profile = await supabase_client.get_profile(user["id"])

    credits_ = profile.get("credits", 0) if profile else 0
    is_premium = profile.get("isPremium", False) if profile else False

    return {
        "id": user["id"],
        "email": user["email"],
        "app_metadata": user["app_metadata"],
        "user_metadata": user["user_metadata"],
        "created_at": user["created_at"],
        "credits": credits_,
        "isPremium": is_premium,
    }


@app.post("/user/profiles-anon/")
async def create_anonymous_profile(data: dict = Body(...)):
    """Create an anonymous user profile with initial credits"""
    anonymous_profile = await supabase_client.create_anonymous_profile(data)
    if not anonymous_profile:
        raise HTTPException(
            status_code=500, detail="Failed to create anonymous user profile"
        )
    return {
        "anon_user_id": anonymous_profile["anon_user_id"],
        "credits": anonymous_profile.get("credits", 0),
        "isAnonymous": True,
    }


if __name__ == "__main__":
    import uvicorn

    HOST = os.environ.get("HOST", "localhost")
    PORT = os.environ.get("PORT", 5000)

    uvicorn.run("main:app", host=HOST, port=int(PORT), reload=True)
