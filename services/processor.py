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
    PROMPT_TEMPLATES,
    MODES_TO_OUTPUT_TOKENS,
    get_system_message,
)
import asyncio


logger = get_logger("processor")


def _infer_output_tokens(mode: str, transcript_text: str) -> int:
    """
    Dynamically scales output token allocation based on input length to optimize
    token economy, summary quality, and user experience.

    Benefits:
    - Prevents over-allocation for short content and under-allocation for long content
    - Maintains appropriate summary length expectations per mode (TLDR vs comprehensive)
    - Includes 3x cap to prevent runaway token usage while ensuring minimum viable output
    - Optimizes LLM performance by providing appropriate output constraints
    """
    mode_str = str(mode).lower()
    base_output_tokens = MODES_TO_OUTPUT_TOKENS.get(mode_str, 1024)

    estimated_input_tokens = len(transcript_text) / CHAR_TO_TOKEN_RATIO

    # Scale output tokens based on input length with a reasonable cap
    # For every additional 1000 input tokens beyond 1000, add 20% more to base output tokens
    input_scale_factor = 1.0
    if estimated_input_tokens > 1000:
        # Calculate scaling factor based on input size (max 3x)
        input_scale_factor = min(
            3.0, 1.0 + ((estimated_input_tokens - 1000) / 1000) * 0.2
        )
        logger.debug(
            f"Scaling output tokens by factor of {input_scale_factor} based on input length"
        )

    # Calculate final output tokens
    max_output_tokens = int(base_output_tokens * input_scale_factor)
    logger.debug(f"Using {max_output_tokens} output tokens for mode {mode}")
    return max_output_tokens


def _truncate_transcript(transcript_text: str) -> str:
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
        max_chars = int(MAX_TRANSCRIPT_TOKENS * CHAR_TO_TOKEN_RATIO)
        original_length = len(transcript_text)
        transcript_text = transcript_text[:max_chars]
        logger.info(
            f"Truncated transcript from {original_length} to {len(transcript_text)} characters"
        )

        truncation_note = f"\n\n[Note: This transcript was truncated from {original_length} characters to {len(transcript_text)} characters due to token limits.]"
        transcript_text += truncation_note

    return transcript_text


def _get_prompt_template(mode: str, prompt_template: Optional[str] = None) -> str:
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
    custom_prompt: Optional[str] = None,
    stream: bool = False,
    tags: Optional[list[str]] = None,
) -> str:
    """
    Process transcript text with LLM.

    Args:
        transcript_text (str): The transcript text to process
        mode (str): The processing mode
        custom_prompt (str, optional): Custom prompt template. Defaults to None.

    Returns:
        str: The LLM response

    Raises:
        HTTPException: If there's an error processing the transcript
    """
    try:
        transcript_text = _truncate_transcript(transcript_text)

        prompt_template = _get_prompt_template(mode, custom_prompt)
        system_message = get_system_message(mode, tags)

        prompt = prompt_template.format(
            transcript=transcript_text,
        )

        chat_completion = await groq_client(
            system_message=system_message,
            prompt=prompt,
            max_output_tokens=_infer_output_tokens(mode, transcript_text),
            stream=stream,
        )
        return chat_completion

    except Exception as e:
        logger.error(f"Error processing transcript with LLM: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing transcript with LLM: {str(e)}"
        )


def _find_stop_word_boundary(text: str, max_chars: int) -> int:
    """
    Find a natural break point in text based on stop words and punctuation.

    Args:
        text (str): The text to find a break point in
        max_chars (int): Maximum number of characters to consider

    Returns:
        int: Index of the break point
    """
    if not text or max_chars <= 0:
        return 0
    if len(text) <= max_chars:
        return len(text)

    stop_words = [".\n", "!\n", "?\n", ". ", "! ", "? ", "\n\n", "; "]

    search_text = text[:max_chars]

    best_pos = -1
    best_stop_len = 0

    for stop_word in stop_words:
        pos = search_text.rfind(stop_word)
        if pos > best_pos:
            best_pos = pos
            best_stop_len = len(stop_word)

    if best_pos != -1:
        return best_pos + best_stop_len

    last_space = search_text.rfind(" ")
    if last_space != -1:
        return last_space + 1

    return max_chars


def _get_chunk_prompt(
    mode: str,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
) -> str:
    """
    Generate a prompt specific to the chunk's position and mode.

    Args:
        mode (str): The processing mode (tldr, key_insights, comprehensive, article)
        chunk (str): The current chunk of text
        chunk_index (int): Index of the current chunk
        total_chunks (int): Total number of chunks
        previous_context (str): Context from previous chunk

    Returns:
        str: Formatted prompt for the chunk
    """
    mode_str = str(mode).lower()

    if mode_str == Modes.COMPREHENSIVE:
        if chunk_index == 0:
            return (
                "Transform this content into a detailed, well-structured piece. "
                "Cover all main topics and important details as if you're the original creator "
                "expanding on your ideas for readers. This is the first part of a longer content:"
                "DO NOT CONCLUDE THE CONTENT. JUST START IT."
                f"\n\n{chunk}"
            )
        elif chunk_index == total_chunks - 1:
            return (
                "This is the final part of the content. "
                "Conclude the comprehensive analysis by tying together all major points, "
                "drawing connections between different sections, and providing a satisfying conclusion:"
                "CONCLUDE THE CONTENT HERE."
                f"\n\n{chunk}"
            )
        else:
            return (
                "Continue the comprehensive analysis of this part of the content. "
                "Maintain the same level of detail and structure as previous parts:"
                "CONTINUE THE CONTENT HERE."
                f"\n\n{chunk}"
            )

    elif mode_str == Modes.ARTICLE:
        if chunk_index == 0:
            return (
                "Rewrite this content as a comprehensive article. "
                "Expand on the ideas, add context, draw connections, and provide deeper insights. "
                "Write in the creator's voice as if they're sharing their expertise with readers. "
                "This is the first part of a longer content:"
                "DO NOT CONCLUDE THE CONTENT. JUST START IT."
                f"\n\n{chunk}"
            )
        elif chunk_index == total_chunks - 1:
            return (
                "This is the final part of the article. "
                "Write a conclusion that synthesizes all major points, "
                "draws meaningful connections, and leaves readers with valuable insights:"
                "CONCLUDE THE CONTENT HERE."
                f"\n\n{chunk}"
            )
        else:
            return (
                "Continue writing the article, maintaining the same style and depth of analysis. "
                "Ensure smooth transitions from previous parts:"
                "CONTINUE THE CONTENT HERE."
                f"\n\n{chunk}"
            )

    return f"Process this part of the content:\n\n{chunk}"


async def process_transcript_in_chunks(
    transcript_text: str,
    mode: str,
    groq_client: Callable,
    custom_prompt: Optional[str] = None,
    stream: bool = False,
    tags: Optional[list[str]] = None,
) -> str:
    """
    Process transcript text with LLM sequentially, maintaining context between chunks.

    Args:
        transcript_text (str): The transcript text to process
        mode (str): The processing mode
        groq_client (Callable): The LLM client function
        custom_prompt (str, optional): Custom prompt template. Defaults to None.
        stream (bool): Whether to stream the response. Defaults to False.
        tags (Optional[list[str]]): List of video tags. Defaults to None.

    Returns:
        str: The combined LLM responses

    Raises:
        HTTPException: If there's an error processing the transcript
    """
    try:
        base_system_message = get_system_message(mode, tags)

        max_chars = int(MAX_TRANSCRIPT_TOKENS * CHAR_TO_TOKEN_RATIO)
        chunks = []
        current_pos = 0

        while current_pos < len(transcript_text):
            chunk_end = (
                _find_stop_word_boundary(transcript_text[current_pos:], max_chars)
                + current_pos
            )
            chunks.append(transcript_text[current_pos:chunk_end])
            current_pos = chunk_end

        combined_response = ""
        previous_context = ""

        for i, chunk in enumerate(chunks):
            if i > 0:
                asyncio.sleep(20)  # Small delay to avoid rate limiting

            chunk_system_message = base_system_message

            if len(chunks) > 1:
                if i == 0:
                    chunk_system_message += (
                        "\n\nThis is the first part of a longer content that will be processed in multiple chunks. "
                        "Write your response as if it's the beginning of a complete piece, "
                        "setting up the context and structure for what follows."
                    )
                elif i == len(chunks) - 1:
                    chunk_system_message += (
                        "\n\nThis is the final part of the content. "
                        "Write a conclusion that ties everything together, "
                        "summarizes the key points, and provides a satisfying ending. "
                        "Make sure to maintain consistency with the previous parts."
                        f"\n\nPrevious context to maintain continuity:\n{previous_context}"
                    )
                else:
                    chunk_system_message += (
                        "\n\nYou are continuing from a previous part of the content. "
                        "Maintain consistency with the previous part and continue naturally."
                        f"\n\nPrevious context to maintain continuity:\n{previous_context}"
                    )

            prompt = _get_chunk_prompt(
                mode=mode,
                chunk=chunk,
                chunk_index=i,
                total_chunks=len(chunks),
            )

            try:
                chunk_response = await groq_client(
                    system_message=chunk_system_message,
                    prompt=prompt,
                    max_output_tokens=_infer_output_tokens(mode, chunk),
                    stream=stream,
                )
            except Exception as e:
                logger.error(f"Error processing chunk {i}: {str(e)}")
                continue

            if isinstance(chunk_response, str):
                combined_response += "\n\n" + chunk_response
                sentences = chunk_response.split(". ")
                previous_context = (
                    ". ".join(sentences[-10:])
                    if len(sentences) > 10
                    else chunk_response
                )
            else:
                async for part in chunk_response:
                    combined_response += part
                    previous_context = part

        return combined_response

    except Exception as e:
        logger.error(f"Error processing transcript sequentially: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing transcript sequentially: {str(e)}",
        )
