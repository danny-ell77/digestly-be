"""
Text processing and LLM integration module for handling transcripts.
"""

from typing import Callable
from typing import Optional
from fastapi import HTTPException
from app.logger import get_logger
from app.models import Modes
from app.prompts import (
    MAX_TRANSCRIPT_TOKENS,
    CHAR_TO_TOKEN_RATIO,
    KEY_INSIGHTS_LENGTH,
    PROMPT_TEMPLATES,
    MODES_TO_OUTPUT_TOKENS,
    get_system_message,
)

# Get logger for this module
logger = get_logger("processor")


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


def get_prompt_template(mode: str, prompt_template: Optional[str] = None) -> str:
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

    # Get the mode-specific template from the dictionary
    mode_str = str(mode).lower()
    if mode_str in PROMPT_TEMPLATES:
        return PROMPT_TEMPLATES[mode_str]
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode: {mode}. Supported modes are: {', '.join([str(m) for m in Modes])}",
        )


async def process_transcript_with_llm(
    transcript_text: str,
    mode: str,
    groq_client: Callable,
    prompt_template: Optional[str] = None,
    stream: bool = False,
    tags: Optional[list[str]] = None,
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
        prompt_template = get_prompt_template(mode, prompt_template)
        system_message = get_system_message(mode, tags)

        # Format the prompt
        prompt = prompt_template.format(
            transcript=transcript_text,
            insight_length=KEY_INSIGHTS_LENGTH,
        )

        chat_completion = await groq_client(
            system_message=system_message,
            prompt=prompt,
            max_output_tokens=MODES_TO_OUTPUT_TOKENS.get(mode, 1024),
            stream=stream,
        )
        return chat_completion

    except Exception as e:
        logger.error(f"Error processing transcript with LLM: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing transcript with LLM: {str(e)}"
        )
