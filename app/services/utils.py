"""
Utility functions for transcript processing.
"""

from app.logger import get_logger
from app.models import DigestMode
from app.prompts import MAX_TRANSCRIPT_TOKENS, CHAR_TO_TOKEN_RATIO

logger = get_logger("transcript_utils")


def truncate_transcript(transcript_text: str) -> str:
    """Truncate transcript if it exceeds token limits."""
    estimated_tokens = len(transcript_text) / CHAR_TO_TOKEN_RATIO

    if estimated_tokens > MAX_TRANSCRIPT_TOKENS:
        max_chars = int(MAX_TRANSCRIPT_TOKENS * CHAR_TO_TOKEN_RATIO)
        original_length = len(transcript_text)
        transcript_text = transcript_text[:max_chars]

        truncation_note = f"\n\n[Note: This transcript was truncated from {original_length} to {len(transcript_text)} characters due to token limits.]"
        transcript_text += truncation_note

        logger.info(
            f"Truncated transcript from {original_length} to {len(transcript_text)} characters"
        )

    return transcript_text


def find_stop_word_boundary(text: str, max_chars: int) -> int:
    """Find natural break point in text."""
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


def infer_output_tokens(mode: str, transcript_text: str) -> int:
    """Dynamically scale output token allocation based on input length."""
    mode_str = str(mode).lower()
    base_output_tokens = {
        DigestMode.TLDR: 1024,
        DigestMode.KEY_INSIGHTS: 2048,
        DigestMode.COMPREHENSIVE: 4096,
        DigestMode.ARTICLE: 4096,
    }.get(mode_str, 1024)

    estimated_input_tokens = len(transcript_text) / CHAR_TO_TOKEN_RATIO

    # Scale output tokens based on input length with a reasonable cap
    input_scale_factor = 1.0
    if estimated_input_tokens > 1000:
        input_scale_factor = min(
            3.0, 1.0 + ((estimated_input_tokens - 1000) / 1000) * 0.2
        )
        logger.debug(
            f"Scaling output tokens by factor of {input_scale_factor} based on input length"
        )

    max_output_tokens = int(base_output_tokens * input_scale_factor)
    logger.debug(f"Using {max_output_tokens} output tokens for mode {mode}")
    return max_output_tokens
