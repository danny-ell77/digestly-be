"""
Text processing and LLM integration module for handling transcripts.
"""

from typing import Callable
from enum import Enum
from typing import Optional
from fastapi import HTTPException
from groq import AsyncGroq
import os
from app.logger import get_logger

# Get logger for this module
logger = get_logger("processor")

# Constants
MAX_TRANSCRIPT_TOKENS = 10000
CHAR_TO_TOKEN_RATIO = 4.0
KEY_INSIGHTS_LENGTH = "5 - 7"
INCLUDE_RESPONSE_FORMAT = "Please format your response as MARKDOWN"


class Modes(str, Enum):
    TLDR = "tldr"
    KEY_INSIGHTS = "key_insights"
    COMPREHENSIVE = "comprehensive"
    ARTICLE = "article"

    def __str__(self):
        return str(self.value)


def truncate_transcript(transcript_text: str) -> str:
    """
    Truncate the transcript text if it's too long.

    Args:
        transcript_text (str): The transcript text to truncate

    Returns:
        str: Truncated transcript text
    """
    # Token safeguard - estimate token count and truncate if necessary
    estimated_tokens = len(transcript_text) / CHAR_TO_TOKEN_RATIO
    logger.debug(
        f"Estimated transcript tokens: {estimated_tokens} from {len(transcript_text)} characters"
    )

    if estimated_tokens > MAX_TRANSCRIPT_TOKENS:
        # Calculate how many characters to keep to stay under the token limit
        max_chars = int(MAX_TRANSCRIPT_TOKENS * CHAR_TO_TOKEN_RATIO)
        original_length = len(transcript_text)
        transcript_text = transcript_text[:max_chars]
        logger.info(
            f"Truncated transcript from {original_length} to {len(transcript_text)} characters"
        )

        # Add a note about truncation
        truncation_note = f"\n\n[Note: This transcript was truncated from {original_length} characters to {len(transcript_text)} characters due to token limits.]"
        transcript_text += truncation_note

    return transcript_text


async def get_prompt_template(mode: str, prompt_template: Optional[str] = None) -> str:
    """
    Get the prompt template based on the mode.

    Args:
        mode (str): The processing mode (tldr, key_insights, comprehensive)
        prompt_template (str, optional): Custom prompt template. Defaults to None.

    Returns:
        str: The prompt template

    Raises:
        HTTPException: If the mode is invalid
    """
    if prompt_template:
        return prompt_template + "\n\n" + "{transcript}"

    # Otherwise use mode-specific templates
    if mode == Modes.TLDR:
        return (
            "Create a very brief TL;DR summary (2-3 sentences maximum) of this video content:"
            "\n\n{transcript}"
        )
    elif mode == Modes.KEY_INSIGHTS:
        return (
            "Extract the {insight_lenght} most important key insights from this video content. "
            "Format each insight as a bullet point with a brief explanation:"
            "\n\n{transcript}"
        )
    elif mode == Modes.COMPREHENSIVE:
        return (
            "Please provide a comprehensive digest of the following video content. "
            "Include main topics, key points, and any important details:"
            "\n\n{transcript}"
        )
    elif mode == Modes.ARTICLE:
        return (
            "Please revise this video content into an article of at least"
            "2000 words. draw insights and compare with real world information"
            "\n\n{transcript}"
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}. Supported modes are: {', '.join([str(m) for m in Modes])}",
        )


async def get_system_message(mode: str) -> str:
    """
    Get the system message based on the mode.

    Args:
        mode (str): The processing mode

    Returns:
        str: The system message
    """
    if mode == Modes.TLDR:
        system_message = "You are a concise video summarizer. Keep responses extremely brief in at least 200 words"
    elif mode == Modes.KEY_INSIGHTS:
        system_message = "You are an insights extractor focusing on the most valuable takeaways. in at least 500 words"
    elif mode == Modes.COMPREHENSIVE:
        system_message = "You are a thorough video analyzer providing detailed, structured comprehensive insights into the video content in at least a 1000 words"
    elif mode == Modes.ARTICLE:
        system_message = "You are a video content to article translator, bringing new insghts from the video."
    else:
        system_message = "You are a video analyzer helping users."

    return system_message + "\n\n" + INCLUDE_RESPONSE_FORMAT


modes_to_output_tokens = {
    Modes.TLDR: 1024,
    Modes.KEY_INSIGHTS: 2048,
    Modes.COMPREHENSIVE: 4096,
    Modes.ARTICLE: 4096,
}


async def process_transcript_with_llm(
    transcript_text: str,
    mode: str,
    groq_client: Callable,
    prompt_template: Optional[str] = None,
    stream: bool = False,
) -> str:
    """
    Process transcript text with LLM.

    Args:
        transcript_text (str): The transcript text to process
        mode (str): The processing mode
        prompt_template (str, optional): Custom prompt template. Defaults to None.

    Returns:
        str: The LLM response

    Raises:
        HTTPException: If there's an error processing the transcript
    """
    try:
        transcript_text = truncate_transcript(transcript_text)

        # Get prompt template and system message
        prompt_template = await get_prompt_template(mode, prompt_template)
        system_message = await get_system_message(mode)

        # Format the prompt
        prompt = prompt_template.format(
            transcript=transcript_text,
            insight_lenght=KEY_INSIGHTS_LENGTH,
        )

        chat_completion = await groq_client(
            system_message=system_message,
            prompt=prompt,
            max_output_tokens=modes_to_output_tokens.get(mode, 1024),
            stream=stream,
        )
        return chat_completion

    except Exception as e:
        logger.error(f"Error processing transcript with LLM: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing transcript with LLM: {str(e)}"
        )


def get_groq_client():
    """Get Groq API client with API key"""
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
        completion = await client.chat.completions.create(
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
        )
        if stream:
            # Handle streaming response
            return completion
        else:
            # Handle non-streaming response
            if not completion.choices or not completion.choices[0].message.content:
                raise ValueError("Empty content received from analysis.")
        return completion.choices[0].message.content

    return get_chat_completion
