import os
import logging
import functools
from typing import AsyncGenerator
from app.decorators import track_usage
from app.model_selector import ModelSelector
from app.auth import CurrentUser
from app.models import (
    TranscriptRequest,
    VideoDataResponse,
    to_digestly_type,
)

from app.db import supabase_client
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from app.services.content_processor import VideoProcessor
from app.services.transcripts.processor import TranscriptProcessor
from app.deps import (
    YoutubeClient,
    GroqClient,
)
from app.prompts import MIND_MAP_PROMPT, MIND_MAP_SYSTEM_MESSAGE

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


@app.get("/transcript/saved/{video_id}")
async def get_saved_transcript(video_id: str):
    """Get saved transcript from database for a video ID"""
    try:
        video_id = extract_video_id(video_id)
        transcript_text = await supabase_client.get_transcript(video_id)

        if not transcript_text:
            raise HTTPException(
                status_code=404,
                detail=f"No saved transcript found for video ID: {video_id}",
            )

        return {
            "video_id": video_id,
            "transcript": transcript_text,
            "size": f"{len(transcript_text.split())} words, {len(transcript_text)} characters",
            "source": "database",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving saved transcript: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving saved transcript: {str(e)}"
        )


@app.get("/mind-map/")
@track_usage
async def build_mind_map(video_id: str, user: CurrentUser, groq_client: GroqClient):
    try:
        transcript = await TranscriptProcessor().fetch_transcript(video_id, "en")
        if not transcript:
            raise HTTPException(
                status_code=404,
                detail=f"No transcript found for video ID: {video_id}",
            )
    except ValueError as e:
        logger.error(f"Transcript not found error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    user_message = MIND_MAP_PROMPT.format(transcript=transcript)
    completion = await groq_client(
        model="llama-3.3-70b-versatile",
        temperature=0.7,
        system_message=MIND_MAP_SYSTEM_MESSAGE,
        prompt=user_message,
        max_output_tokens=7000,
        stream=False,
        # reasoning_format="hidden",
        response_format={"type": "json_object"},
    )
    return {"video_id": video_id, "map": completion}


if __name__ == "__main__":
    import uvicorn

    HOST = os.environ.get("HOST", "localhost")
    PORT = os.environ.get("PORT", 10000)

    uvicorn.run("main:app", host=HOST, port=int(PORT), reload=True)
