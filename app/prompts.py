"""
Prompt templates and system messages for different processing modes.
"""

from typing import Optional
from app.models import Modes

# Constants
MAX_TRANSCRIPT_TOKENS = 10000
CHAR_TO_TOKEN_RATIO = 4.0
KEY_INSIGHTS_LENGTH = "5 - 7"
INCLUDE_RESPONSE_FORMAT = "Please format your response as MARKDOWN"
TAG_BASED_RESPONSE_FORMAT = (
    "Please provide a response based on the following tags: {tags}"
)
PROGRAMMING_FORMAT_RESPONSE = (
    "Please provide COMPREHENSIVE CODE SAMPLES in MARKDOWN FORMAT based on the prompt"
)
MATH_FORMAT_RESPONSE = (
    "Please provide COMPREHENSIVE MATH FORMULAS in MARKDOWN FORMAT based on the prompt"
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
        "Create a very brief TL;DR summary (2-3 sentences maximum) of this video content:"
        "\n\n{transcript}"
    ),
    Modes.KEY_INSIGHTS: (
        "Extract the 5 - 7 most important key insights from this video content. "
        "Format each insight as a bullet point with a brief explanation:"
        "\n\n{transcript}"
    ),
    Modes.COMPREHENSIVE: (
        "Please provide a comprehensive digest of the following video content. "
        "Include main topics, key points, and any important details:"
        "\n\n{transcript}"
    ),
    Modes.ARTICLE: (
        "Please revise this video content into an article of at least"
        "2000 words. draw insights and compare with real world information"
        "\n\n{transcript}"
    ),
}

DEFAULT_PROMPT_TEMPLATE = (
    "You are a video analyzer helping users."
    " Please provide a detailed analysis of the video content."
    "\n\n{transcript}"
)

# System messages for different modes
SYSTEM_MESSAGES = {
    Modes.TLDR: "You are a concise video summarizer. Keep responses extremely brief in at least 200 words",
    Modes.KEY_INSIGHTS: "You are an insights extractor focusing on the most valuable takeaways. in at least 500 words",
    Modes.COMPREHENSIVE: "You are a thorough video analyzer providing detailed, structured comprehensive insights into the video content in at least a 1000 words",
    Modes.ARTICLE: "You are a video content to article translator, bringing new insights from the video.",
}

DEFAULT_SYSTEM_MESSAGE = (
    "You are a video analyzer helping users. Please provide a detailed analysis of the video content."
    " Keep responses extremely brief in at least 200 words"
)


def get_system_message(mode: Modes, tags: Optional[list[str]]) -> str:
    """
    Get the system message for article mode with tag-specific formatting.

    Args:
        tags (Optional[list[str]]): List of video tags

    Returns:
        str: System message with tag-specific formatting
    """
    message = SYSTEM_MESSAGES.get(mode, DEFAULT_SYSTEM_MESSAGE)

    if tags:
        # This is a simplifed cheack. In the future, we can use a more sophisticated method
        # to check if the tags are related to programming or math like tokenization
        if set(tags) & set(PROGRAMMING_TAGS):
            message += f" {PROGRAMMING_FORMAT_RESPONSE}"
        elif set(tags) & set(MATH_TAGS):
            message += f" {MATH_FORMAT_RESPONSE}"

    return message + "\n\n" + INCLUDE_RESPONSE_FORMAT
