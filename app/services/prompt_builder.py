"""
Prompt builder for constructing prompts with different components.
"""

from typing import Optional, List, Dict, Any, NamedTuple
from app.logger import get_logger
from app.prompts import (
    get_system_message,
    get_prompt_template,
    get_chunk_prompt,
    get_chunk_system_message,
)

logger = get_logger("prompt_builder")


class Prompt(NamedTuple):
    """Container for system message and prompt."""

    system_message: str
    user_message: str


class PromptBuilder:
    """Builder class for constructing prompts with different components."""

    def __init__(self):
        self._components: Dict[str, Any] = {}
        self._system_message = ""
        self._prompt = ""
        self._tags: Optional[List[str]] = None

    def with_mode(self, mode: str) -> "PromptBuilder":
        """Set the processing mode."""
        self._components["mode"] = mode
        return self

    def with_tags(self, tags: Optional[List[str]]) -> "PromptBuilder":
        """Set the video tags."""
        self._tags = tags
        return self

    def with_transcript(self, transcript: str) -> "PromptBuilder":
        """Set the transcript text."""
        self._components["transcript"] = transcript
        return self

    def with_custom_prompt(self, prompt: Optional[str]) -> "PromptBuilder":
        """Set a custom prompt template."""
        if prompt is not None:
            self._components["custom_prompt"] = prompt
        return self

    def with_chunk_info(
        self, chunk: str, chunk_index: int, total_chunks: int
    ) -> "PromptBuilder":
        """Set chunk-specific information."""
        self._components.update(
            {"chunk": chunk, "chunk_index": chunk_index, "total_chunks": total_chunks}
        )
        return self

    def with_previous_context(self, context: str) -> "PromptBuilder":
        """Set the previous context for chunked processing."""
        self._components["previous_context"] = context
        return self

    def _build_system_message(self) -> str:
        """Build the system message based on components."""
        mode = self._components.get("mode")
        if not mode:
            raise ValueError("Mode is required to build system message")

        base_system_message = get_system_message(mode, self._tags)

        if "chunk" in self._components:
            return get_chunk_system_message(
                base_system_message=base_system_message,
                chunk_index=self._components["chunk_index"],
                total_chunks=self._components["total_chunks"],
                previous_context=self._get_previous_context(),
            )

        return base_system_message

    def _get_previous_context(self) -> str:
        """Get the previous context for chunked processing."""
        if context := self._components.get("previous_context", ""):
            return context
        logger.warning("No previous context provided.")
        return ""

    def _build_prompt(self) -> str:
        """Build the prompt based on components."""
        mode = self._components.get("mode")
        if not mode:
            raise ValueError("Mode is required to build prompt")
        prompt = ""

        if {"custom_prompt", "transcript"}.issubset(self._components.keys()):
            prompt += self._components["transcript"] + "\n\n"
            prompt += self._components["custom_prompt"]
            return prompt

        if "chunk" in self._components:
            prompt += get_chunk_prompt(
                mode=mode,
                chunk=self._components["chunk"],
                chunk_index=self._components["chunk_index"],
                total_chunks=self._components["total_chunks"],
            )
            return prompt

        # Fallback to default prompt template if no custom prompt is provided
        prompt_template = get_prompt_template(mode)
        return prompt_template.format(transcript=self._components["transcript"])

    def build(self) -> Prompt:
        """Build and return the complete prompt (system_message, prompt)."""
        return Prompt(
            system_message=self._build_system_message(),
            user_message=self._build_prompt(),
        )
