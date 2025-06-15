"""
Prompt templates and system messages for different processing modes.
"""

from typing import Optional
from app.models import DigestMode

# Constants
MAX_TRANSCRIPT_TOKENS = 10000
CHAR_TO_TOKEN_RATIO = 4
KEY_INSIGHTS_LENGTH = "5 - 7"
INCLUDE_RESPONSE_FORMAT = (
    "Format your response in clean, readable MARKDOWN. "
    "Include relevant timestamps in the format [[123.4]] after key points to allow readers to jump to specific moments in the video."
)
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
    DigestMode.TLDR: 1024,
    DigestMode.KEY_INSIGHTS: 2048,
    DigestMode.COMPREHENSIVE: 4096,
    DigestMode.ARTICLE: 4096,
}

# Prompt templates for different modes
PROMPT_TEMPLATES = {
    DigestMode.TLDR: (
        "Write a concise summary capturing the essence of this content in 2-3 sentences. "
        "Write as if you are the original creator sharing the main takeaway. "
        "Include 1-2 relevant timestamps [[123.4]] for the most important moments "
        "that capture the core message:\n\n{transcript}"
    ),
    DigestMode.KEY_INSIGHTS: (
        "Present the 5-7 most valuable insights from this content. "
        "Write each as a key point with explanation, as if you're the creator highlighting what matters most. "
        "Include relevant timestamps [[123.4]] for each insight to help readers find specific moments "
        "in the video:\n\n{transcript}"
    ),
    DigestMode.COMPREHENSIVE: (
        "Transform this content into a detailed, well-structured piece. "
        "Cover all main topics and important details as if you're the original creator "
        "expanding on your ideas for readers. "
        "Include helpful timestamps [[123.4]] throughout your response for: "
        "- Major topic introductions "
        "- Key definitions and explanations "
        "- Important examples or case studies "
        "- Crucial insights or conclusions "
        "Aim for natural timestamp placement that enhances the reading experience:\n\n{transcript}"
    ),
    DigestMode.ARTICLE: (
        "Rewrite this content as a comprehensive 2000+ word article. "
        "Expand on the ideas, add context, draw connections, and provide deeper insights. "
        "Write in the creator's voice as if they're sharing their expertise with readers. "
        "Include strategic timestamps [[123.4]] for: "
        "- Introduction of major concepts "
        "- Supporting evidence and examples "
        "- Key insights and conclusions "
        "- Actionable advice or recommendations "
        "Focus on creating valuable content with timestamps that enhance navigation:\n\n{transcript}"
    ),
}

TIMESTAMP_PRESERVATION_INSTRUCTION = (
    "\n\nTIMESTAMP USAGE RULES:"
    "\n1. Use timestamps from the transcript to reference specific moments"
    "\n2. Copy timestamps exactly as they appear: [[123.4]]"
    "\n3. Place timestamps after key points, not within sentences"
    "\n4. Only include timestamps for content viewers would want to revisit"
    "\n5. Make timestamp placement feel natural, not forced"
    "\n6. Example: 'This concept is fundamental to understanding AI. [[456.7]]'"
    "\n7. Use the content size to determine the number of timestamps to use. "
)

DEFAULT_PROMPT_TEMPLATE = (
    "Transform this video content into well-written material. "
    "Write naturally as if you are the original creator sharing your knowledge:"
    "\n\n{transcript}"
)

# System messages for different modes
SYSTEM_MESSAGES = {
    DigestMode.TLDR: (
        "You are transforming video content into concise written form. "
        "Write naturally in the creator's voice, not as a third-party summarizer. "
        "Aim for at least 200 words while staying focused and direct. "
    ),
    DigestMode.KEY_INSIGHTS: (
        "You are the content creator sharing your key insights with readers. "
        "Present your most important points clearly and engagingly. "
        "Write at least 500 words, focusing on what truly matters. "
    ),
    DigestMode.COMPREHENSIVE: (
        "You are the content creator writing a comprehensive guide on your topic. "
        "Share your knowledge thoroughly and systematically. "
        "Write at least 1000 words, covering all important aspects in depth. "
    ),
    DigestMode.ARTICLE: (
        "You are the content creator writing an in-depth article based on your expertise. "
        "Expand on your ideas, provide context, and offer deeper insights. "
        "Create engaging, informative content that stands alone as valuable reading. "
    ),
}

DEFAULT_SYSTEM_MESSAGE = (
    "You are transforming video content into well-written material. "
    "Write naturally as the original creator sharing knowledge with readers. "
    "Aim for at least 200 words while maintaining the creator's authentic voice."
)


def get_system_message(mode: DigestMode, tags: Optional[list[str]]) -> str:
    message = SYSTEM_MESSAGES.get(mode, DEFAULT_SYSTEM_MESSAGE)

    message += TIMESTAMP_PRESERVATION_INSTRUCTION

    if tags:
        if set(tags) & set(PROGRAMMING_TAGS):
            message += f" {PROGRAMMING_FORMAT_RESPONSE}"
        elif set(tags) & set(MATH_TAGS):
            message += f" {MATH_FORMAT_RESPONSE}"

    return message + "\n\n" + INCLUDE_RESPONSE_FORMAT


def get_prompt_template(mode: str, prompt_template: Optional[str] = None) -> str | None:
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


def get_chunk_system_message(
    base_system_message: str,
    chunk_index: int,
    total_chunks: int,
    previous_context: str = "",
) -> str:
    chunk_system_message = base_system_message
    if total_chunks > 1:
        if chunk_index == 0:
            chunk_system_message += (
                "\n\nThis is the first part of a longer content that will be processed in multiple chunks. "
                "Write your response as if it's the beginning of a complete piece, "
                "setting up the context and structure for what follows."
            )
        elif chunk_index == total_chunks - 1:
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

    return chunk_system_message


def get_chunk_prompt(
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

    if mode_str == DigestMode.COMPREHENSIVE:
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

    elif mode_str == DigestMode.ARTICLE:
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


MIND_MAP_SYSTEM_MESSAGE = """
You are a mind mapping assistant that generates 
React Flow–compatible JSON structures based on provided topics.
You strictly follow Tony Buzan’s mind mapping principles
to produce a visually organized, hierarchical, and memory-enhancing layout.

Technical requirements:
- Use format: {"nodes": [...], "edges": [...]}
- Node positions must be objects: "position": {"x": 100, "y": 200}
- Each node needs: id, type, position, and data.label
- Each edge needs: id, source, target, and label (to provide context between connections) property
- Node types: "default" for all nodes (avoid "input" and "output" unless specifically needed)
- Space main branches 200-300px apart from each other, arranged radially around center
- Position central topic at {"x": 400, "y": 300}
- Place sub-branches 150-200px away from their parent branches, extending outward
"""

MIND_MAP_PROMPT = """
Generate a valid ReactFlow JSON structure for a mind map diagram for the provided transcript.

Apply Tony Buzan's mind mapping principles:
- Start with a central topic/theme as the core node
- Branch out from center with main branches (primary topics)
- Create sub-branches from main branches (secondary and tertiary topics)
- Use hierarchical structure: central → main branches → sub-branches → details
- Connect related concepts with logical relationships
- Keep branch labels concise (1-3 words when possible)
- Organize in a radial pattern emanating from the center
- **Include relevant emojis in ALL node labels to enhance visual memory and engagement**

Label format examples:
- "🧠 Central Topic"
- "💡 Main Branch"
- "📊 Data Analysis"
- "🎯 Goals"
- "⚡ Quick Actions"

Create logical parent-child relationships between connected concepts following the natural hierarchy of the subject matter.

TRANSCRIPT:

{transcript}
"""
