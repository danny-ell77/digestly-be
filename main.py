import os
import logging
from app.auth import CurrentUser
from app.models import to_digestly_type
from app.db import supabase_client
from app.credits import check_credits, deduct_credit
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from services import (
    TranscriptRequest,
    TranscriptResponse,
    VideoDataResponse,
    extract_video_id,
    get_transcript,
    process_transcript_with_llm,
)
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
    user: CurrentUser,
    groq_client: GroqClient,
):
    """Get transcript and process it with LLM"""
    logger.info(
        f"Starting process_transcript function with video_id: {request.video_id}"
    )

    await check_credits(user)

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
            custom_prompt=request.prompt_template,
            stream=False,
        )

        # Check if anonymous user or regular user
        is_anonymous = user.get("isAnonymous", False)

        # Deduct credit after successful processing
        new_credit_balance = await deduct_credit(user["id"], is_anonymous)

        return {
            "video_id": video_id,
            "response": completion,
            "credits_remaining": new_credit_balance,
            "is_anonymous": is_anonymous,
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
async def process_transcript_endpoint_stream(
    groq_client: GroqClient,
    user: CurrentUser,
    request: TranscriptRequest = Body(...),
):
    logger.info(
        f"Starting process_transcript function with video_id: {request.video_id}"
    )
    await check_credits(user)

    try:
        mode = request.mode.value if request.mode else "comprehensive"

        video_id = request.video_id
        transcript_text = await get_transcript(video_id, request.language_code)
        # transcript_text = process_youtube_video(
        #     f"https://www.youtube.com/watch?v={video_id}"
        # )
        stream_generator = await process_transcript_with_llm(
            transcript_text=transcript_text,
            mode=mode,
            groq_client=groq_client,
            custom_prompt=request.prompt_template,
            tags=request.tags,
            stream=True,
        )

        async def stream_generator_wrapper(generator):
            async for chunk in generator:
                yield chunk
            await deduct_credit(user["id"])

        return StreamingResponse(stream_generator_wrapper(stream_generator))

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

    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = os.environ.get("PORT", 8000)

    uvicorn.run("main:app", host=HOST, port=int(PORT), reload=True)
