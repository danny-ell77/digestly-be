"""
Prompt templates and system messages for different processing modes.
"""

from typing import Optional
from app.models import Modes

# Constants
MAX_TRANSCRIPT_TOKENS = 10000
CHAR_TO_TOKEN_RATIO = 4.0
KEY_INSIGHTS_LENGTH = "5 - 7"
INCLUDE_RESPONSE_FORMAT = "Format your response in clean, readable MARKDOWN"
TAG_BASED_RESPONSE_FORMAT = "Focus on these relevant topics: {tags}"
PROGRAMMING_FORMAT_RESPONSE = (
    "Include practical code examples and implementations in MARKDOWN format"
)
MATH_FORMAT_RESPONSE = (
    "Include mathematical formulas, equations, and worked examples in MARKDOWN format"
)

# Programming-related YouTube video tags
PROGRAMMING_TAGS = [
    "python programming",
    "web development",
    "javascript tutorial",
    "coding basics",
    "software engineering",
    "data structures",
    "algorithms",
    "full stack",
    "machine learning",
    "database design",
    "api development",
    "coding interview",
    "backend development",
    "frontend development",
    "devops",
    "full stack",
    "typescript",
    "javascript",
    "react",
    "programming",
    "programmer",
]

MATH_TAGS = [
    "mathematics",
    "calculus",
    "linear algebra",
    "statistics",
    "probability",
    "algebra",
    "geometry",
    "trigonometry",
    "discrete math",
    "mathematical proofs",
    "number theory",
    "differential equations",
    "optimization",
    "numerical methods",
    "mathematical modeling",
    "data analysis",
    "mathematical logic",
    "set theory",
    "graph theory",
    "topology",
]

# Mode-specific output token limits
MODES_TO_OUTPUT_TOKENS = {
    Modes.TLDR: 1024,
    Modes.KEY_INSIGHTS: 2048,
    Modes.COMPREHENSIVE: 4096,
    Modes.ARTICLE: 4096,
}

# Prompt templates for different modes
PROMPT_TEMPLATES = {
    Modes.TLDR: (
        "Write a concise summary capturing the essence of this content in 2-3 sentences. "
        "Write as if you are the original creator sharing the main takeaway:"
        "\n\n{transcript}"
    ),
    Modes.KEY_INSIGHTS: (
        "Present the 5-7 most valuable insights from this content. "
        "Write each as a key point with explanation, as if you're the creator highlighting what matters most:"
        "\n\n{transcript}"
    ),
    Modes.COMPREHENSIVE: (
        "Transform this content into a detailed, well-structured piece. "
        "Cover all main topics and important details as if you're the original creator "
        "expanding on your ideas for readers:"
        "\n\n{transcript}"
    ),
    Modes.ARTICLE: (
        "Rewrite this content as a comprehensive 2000+ word article. "
        "Expand on the ideas, add context, draw connections, and provide deeper insights. "
        "Write in the creator's voice as if they're sharing their expertise with readers:"
        "\n\n{transcript}"
    ),
}

DEFAULT_PROMPT_TEMPLATE = (
    "Transform this video content into well-written material. "
    "Write naturally as if you are the original creator sharing your knowledge:"
    "\n\n{transcript}"
)

# System messages for different modes
SYSTEM_MESSAGES = {
    Modes.TLDR: (
        "You are transforming video content into concise written form. "
        "Write naturally in the creator's voice, not as a third-party summarizer. "
        "Aim for at least 200 words while staying focused and direct."
    ),
    Modes.KEY_INSIGHTS: (
        "You are the content creator sharing your key insights with readers. "
        "Present your most important points clearly and engagingly. "
        "Write at least 500 words, focusing on what truly matters."
    ),
    Modes.COMPREHENSIVE: (
        "You are the content creator writing a comprehensive guide on your topic. "
        "Share your knowledge thoroughly and systematically. "
        "Write at least 1000 words, covering all important aspects in depth."
    ),
    Modes.ARTICLE: (
        "You are the content creator writing an in-depth article based on your expertise. "
        "Expand on your ideas, provide context, and offer deeper insights. "
        "Create engaging, informative content that stands alone as valuable reading."
    ),
}

DEFAULT_SYSTEM_MESSAGE = (
    "You are transforming video content into well-written material. "
    "Write naturally as the original creator sharing knowledge with readers. "
    "Aim for at least 200 words while maintaining the creator's authentic voice."
)


def get_system_message(mode: Modes, tags: Optional[list[str]]) -> str:
    """
    Get the system message for article mode with tag-specific formatting.

    Args:
        mode (Modes): Processing mode
        tags (Optional[list[str]]): List of video tags

    Returns:
        str: System message with tag-specific formatting
    """
    message = SYSTEM_MESSAGES.get(mode, DEFAULT_SYSTEM_MESSAGE)

    if tags:
        # Check for programming or math content to add specialized formatting
        if set(tags) & set(PROGRAMMING_TAGS):
            message += f" {PROGRAMMING_FORMAT_RESPONSE}"
        elif set(tags) & set(MATH_TAGS):
            message += f" {MATH_FORMAT_RESPONSE}"

    return message + "\n\n" + INCLUDE_RESPONSE_FORMAT


def get_prompt_template(
    mode: str, prompt_template: Optional[str] = None
) -> str | None:
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
    return PROMPT_TEMPLATES.get(mode_str)
