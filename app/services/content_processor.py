"""
Simplified transcript processing service that handles both single-pass and chunked processing.
"""

from typing import Optional, List, Callable, AsyncGenerator
from app.logger import get_logger
from app.prompts import (
    MAX_TRANSCRIPT_TOKENS,
    CHAR_TO_TOKEN_RATIO,
)
from app.services.utils import (
    truncate_transcript,
    find_stop_word_boundary,
    infer_output_tokens,
)
from app.services.prompt_builder import PromptBuilder


logger = get_logger("transcript_service")

CONCLUSION_MARKERS = ["# Conclusion", "## Conclusion", "### Conclusion"]


class VideoProcessor:
    def __init__(self, llm_client: Callable):
        self.llm_client = llm_client

    async def process(
        self,
        transcript_text: str,
        mode: str,
        custom_prompt: Optional[str] = None,
        stream: bool = False,
        tags: Optional[List[str]] = None,
        duration: int = 0,
        max_tokens: int = MAX_TRANSCRIPT_TOKENS,
    ) -> str | AsyncGenerator[str, None]:
        """
        Process a transcript using the appropriate strategy.

        Args:
            transcript_text: The transcript to process
            mode: The processing mode (TLDR, KEY_INSIGHTS, COMPREHENSIVE, ARTICLE)
            custom_prompt: Optional custom prompt template
            stream: Whether to stream the response
            tags: Optional list of video tags

        Returns:
            The processed transcript
        """
        try:
            if duration <= 2400 and stream:
                transcript_text = truncate_transcript(transcript_text)
                return await self._process_single_pass(
                    transcript_text, mode, custom_prompt, tags, stream=True
                )
            else:
                return await self._process_chunked(
                    transcript_text, mode, custom_prompt, tags, max_tokens, stream=False
                )

        except Exception as e:
            logger.error(f"Error processing transcript: {str(e)}")
            raise

    async def _process_single_pass(
        self,
        transcript_text: str,
        mode: str,
        custom_prompt: Optional[str],
        tags: Optional[List[str]],
        stream: bool,
    ) -> str | AsyncGenerator[str, None]:
        """Process transcript in a single pass."""
        prompt = (
            PromptBuilder()
            .with_mode(mode)
            .with_tags(tags)
            .with_transcript(transcript_text)
            .with_custom_prompt(custom_prompt)
            .build()
        )

        response = await self.llm_client(
            system_message=prompt.system_message,
            prompt=prompt.user_message,
            max_output_tokens=infer_output_tokens(mode, transcript_text),
            stream=stream,
        )

        return response

    async def _process_chunked(
        self,
        transcript_text: str,
        mode: str,
        custom_prompt: Optional[str],
        tags: Optional[List[str]],
        max_tokens: int,
        stream: bool,
    ) -> str:
        """Process transcript in chunks."""
        import asyncio

        max_chars = int(max_tokens * CHAR_TO_TOKEN_RATIO)
        chunks = []
        current_pos = 0

        while current_pos < len(transcript_text):
            chunk_end = (
                find_stop_word_boundary(transcript_text[current_pos:], max_chars)
                + current_pos
            )
            chunks.append(transcript_text[current_pos:chunk_end])
            current_pos = chunk_end

        combined_response = ""
        previous_context = ""
        logger.info(
            f"Processing {len(chunks)} chunks for mode '{mode}' with tags: {tags}"
        )
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(5)

            prompt = (
                PromptBuilder()
                .with_mode(mode)
                .with_tags(tags)
                .with_chunk_info(chunk, i, len(chunks))
                .with_previous_context(previous_context)
                .build()
            )
            try:
                chunk_response = await self.llm_client(
                    system_message=prompt.system_message,
                    prompt=prompt.user_message,
                    max_output_tokens=infer_output_tokens(mode, chunk),
                    stream=stream,
                )
            except Exception as e:
                logger.error(f"Error processing chunk: {str(e)}")
                chunk_response = ""

            if isinstance(chunk_response, str) and i < len(chunks) - 1:
                for marker in CONCLUSION_MARKERS:
                    if marker in chunk_response:
                        chunk_response = chunk_response.split(marker)[0].strip()

                combined_response += "\n\n" + chunk_response
                sentences = chunk_response.split(". ")
                previous_context = (
                    ". ".join(sentences[-10:])
                    if len(sentences) > 10
                    else chunk_response
                )

        await asyncio.sleep(5)
        prompt = (
            PromptBuilder()
            .with_mode(mode)
            .with_tags(tags)
            .with_transcript(combined_response)
            .with_custom_prompt(custom_prompt)
            .build()
        )
        try:
            final_response = await self.llm_client(
                system_message=prompt.system_message,
                prompt=prompt.user_message,
                max_output_tokens=infer_output_tokens(mode, combined_response),
                stream=False,
            )
        except Exception as e:
            logger.error(f"Error processing final response: {str(e)}")
            final_response = combined_response

        return final_response.strip()
