import os
import logging
import googleapiclient.discovery
from groq import AsyncGroq
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Any

from services import (
    process_transcript_with_llm,
    extract_video_id,
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


def get_youtube_client():
    import httplib2

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("YouTube API key not found, skipping YouTube Data API")
        raise ValueError("YouTube API key not set")

    # Create an HTTP object with timeouts
    http = httplib2.Http(timeout=10)  # 10 second timeout

    # Create a YouTube API client with the HTTP object
    return googleapiclient.discovery.build(
        "youtube", "v3", developerKey=api_key, http=http
    )


def get_groq_client():
    """Get Groq API client with API key"""
    import asyncio

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=500, detail="GROQ_API_KEY not set in environment"
        )

    client = AsyncGroq(api_key=api_key)

    async def get_chat_completion(
        system_message: str, prompt: str, max_output_tokens: int, stream: bool = False
    ):
        """Get chat completion from Groq API"""
        try:
            # Add a timeout of 30 seconds to prevent hanging
            completion = await asyncio.wait_for(
                client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": system_message,
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.5,
                    max_completion_tokens=max_output_tokens,
                    top_p=1,
                    stop=None,
                    stream=stream,
                ),
                timeout=30.0,  # 30 second timeout
            )

            if stream:
                # Handle streaming response
                return completion
            else:
                # Handle non-streaming response
                if not completion.choices or not completion.choices[0].message.content:
                    raise ValueError("Empty content received from analysis.")
            return completion.choices[0].message.content

        except asyncio.TimeoutError:
            logger.error("Groq API call timed out after 30 seconds")
            raise HTTPException(
                status_code=504,
                detail="Request timed out while waiting for the LLM response",
            )

    return get_chat_completion


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
            tags=request.tags,
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
    client: Any = Depends(get_youtube_client),
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

        with open("video_data.json", "w") as f:
            import json

            json.dump(video_data, f, indent=4)

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
            "tags": snippet.get("tags", []),
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

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
