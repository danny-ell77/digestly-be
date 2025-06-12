import logging
from app.settings import settings
from typing import Annotated
from fastapi import Depends
import googleapiclient.discovery
from fastapi import HTTPException
from groq import AsyncGroq
from groq._types import NOT_GIVEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("digestly")


def get_youtube_client():
    import httplib2

    http = httplib2.Http(timeout=10)  # 10 second timeout

    return googleapiclient.discovery.build(
        "youtube", "v3", developerKey=settings.youtube_api_key, http=http
    )


def get_groq_client():
    """Get Groq API client with API key"""
    import asyncio

    client = AsyncGroq(api_key=settings.groq_api_key)

    async def get_chat_completion(
        model: str,
        temperature: float,
        system_message: str,
        prompt: str,
        max_output_tokens: int,
        stream: bool = False,
    ):
        """Get chat completion from Groq API"""
        try:
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
                    model=model,
                    temperature=temperature,
                    max_completion_tokens=max_output_tokens,
                    top_p=1,
                    stop=None,
                    stream=stream,
                    reasoning_format=(
                        "hidden"
                        if model == "deepseek-r1-distill-llama-70b"
                        else NOT_GIVEN
                    ),
                ),
                timeout=300.0,  # 300 second timeout
            )

            if stream:

                async def stream_generator_wrapper():
                    async for chunk in completion:
                        content = chunk.choices[0].delta.content
                        if content:
                            yield content

                return stream_generator_wrapper()

            else:
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


YoutubeClient = Annotated[
    googleapiclient.discovery.Resource, Depends(get_youtube_client)
]
GroqClient = Annotated[AsyncGroq, Depends(get_groq_client)]
