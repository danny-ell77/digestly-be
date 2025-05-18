import os
import googleapiclient.discovery
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Any

from services import (
    process_transcript_with_llm,
    extract_video_id,
    get_groq_client,
    get_transcript,
    TranscriptRequest,
    TranscriptResponse,
    VideoDataResponse,
)


load_dotenv()
logger = logging.getLogger("tube-talk")

app = FastAPI(
    title="YouTube Video Processor",
    description="API for processing YouTube videos with LLMs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


@app.get("/")
async def root():
    return {"message": "YouTube Video Processor API is running"}


@app.post("/transcript/", response_model=TranscriptResponse)
async def get_transcript_endpoint(request: TranscriptRequest):
    """Get transcript from YouTube video ID"""
    try:
        video_id = request.video_id
        transcript_text = await get_transcript(video_id, request.language_code)

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
async def process_transcript_endpoint(
    request: TranscriptRequest,
    groq_client: Any = Depends(get_groq_client),
):
    """Get transcript and process it with LLM"""
    logger.info(
        f"Starting process_transcript function with video_id: {request.video_id}"
    )
    try:
        # result = await process_youtube_video_in_segments(
        #     youtube_url=f"https://www.youtube.com/watch?v={request.video_id}"
        # )
        video_id = request.video_id
        transcript_text = await get_transcript(video_id, request.language_code)

        mode = request.mode.value if request.mode else "comprehensive"
        completion = await process_transcript_with_llm(
            transcript_text=transcript_text,
            mode=mode,
            groq_client=groq_client,
            prompt_template=request.prompt_template,
            stream=False,
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
async def process_transcript_endpoint_strem(
    request: TranscriptRequest,
    groq_client: Any = Depends(get_groq_client),
):
    logger.info(
        f"Starting process_transcript function with video_id: {request.video_id}"
    )
    try:
        # result = await process_youtube_video_in_segments(
        #     youtube_url=f"https://www.youtube.com/watch?v={request.video_id}"
        # )
        video_id = request.video_id
        transcript_text = await get_transcript(video_id, request.language_code)

        mode = request.mode.value if request.mode else "comprehensive"
        completion = await process_transcript_with_llm(
            transcript_text=transcript_text,
            mode=mode,
            groq_client=groq_client,
            prompt_template=request.prompt_template,
            stream=True,
        )

        async def stream_generator_wrapper():
            async for chunk in completion:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        return StreamingResponse(stream_generator_wrapper())

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
    # client: Any = Depends(get_youtube_client),
):
    """Fetch metadata for a YouTube video"""
    logger.info(f"Fetching video metadata for video_id: {video_id}")
    try:
        try:
            video_id = extract_video_id(video_id)
        except (ValueError, NameError):
            pass

        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            logger.warning("YouTube API key not found, skipping YouTube Data API")
            raise ValueError("YouTube API key not set")

        # Create a YouTube API client
        client = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)

        video_data = (
            client.videos()
            .list(part="snippet,contentDetails,statistics", id=video_id)
            .execute()
        )

        if not video_data.get("items"):
            logger.warning(f"No video found with ID: {video_id}")
            raise ValueError(f"No video found with ID: {video_id}")

        video_info = video_data["items"][0]
        snippet = video_info["snippet"]
        statistics = video_info.get("statistics", {})

        # Format the response
        return {
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail_url": snippet.get("thumbnails", {})
            .get("high", {})
            .get("url", ""),
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)),
            "comment_count": int(statistics.get("commentCount", 0)),
            "duration": video_info.get("contentDetails", {}).get("duration", ""),
        }
    except ValueError as e:
        logger.error(f"Video not found error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching video metadata: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching video metadata: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
