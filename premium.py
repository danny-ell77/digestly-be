import os
import math
import pytube
from groq import Groq
from io import BytesIO
import tempfile
from pydub import AudioSegment
import asyncio
import time
from typing import Optional
import urllib.parse
from backoff import on_exception, expo

# Constants
DEFAULT_SEGMENT_SIZE_MINUTES = 5
MAX_RETRIES = 3


class TranscriptionError(Exception):
    """Custom exception for transcription errors."""

    pass


class AnalysisError(Exception):
    """Custom exception for analysis errors."""

    pass


def is_valid_youtube_url(url: str) -> bool:
    """Check if a URL is a valid YouTube URL."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        return (
            parsed_url.netloc in ("www.youtube.com", "youtube.com", "m.youtube.com")
            and "v=" in parsed_url.query
        )
    except Exception:
        return False


def get_video_length(youtube_url: str) -> int:
    """Get the length of a YouTube video in seconds."""
    try:
        yt = pytube.YouTube(youtube_url)
        return yt.length
    except Exception as e:
        print(f"Error getting video length: {e}")
        return 0


@on_exception(expo, pytube.exceptions.PytubeError, max_tries=MAX_RETRIES)
def download_youtube_audio_segment(
    youtube_url: str, start_seconds: int, end_seconds: int
) -> Optional[BytesIO]:
    """Download a specific segment of a YouTube video's audio with retry."""
    try:
        # Download audio to a temporary file
        yt = pytube.YouTube(youtube_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if audio_stream is None:
            print("No audio stream found")
            return None
        temp_file = audio_stream.download()

        # Convert to audio segment
        audio = AudioSegment.from_file(temp_file)

        # Extract the requested segment (convert seconds to milliseconds)
        start_ms = start_seconds * 1000
        end_ms = end_seconds * 1000
        segment = audio[start_ms:end_ms]

        # Create a BytesIO buffer for the segment
        buffer = BytesIO()
        segment.export(buffer, format="mp3")
        buffer.seek(0)

        # Clean up
        os.remove(temp_file)

        print(f"Downloaded audio segment {start_seconds}-{end_seconds} seconds")
        return buffer
    except Exception as e:
        print(f"Error downloading segment {start_seconds}-{end_seconds}: {e}")
        raise  # Re-raise the exception for the retry mechanism


@on_exception(expo, Exception, max_tries=MAX_RETRIES)
def transcribe_audio_segment(audio_buffer: BytesIO) -> str:
    """Transcribe an audio segment with retry."""
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(audio_buffer.getvalue())

        with open(temp_filename, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(file=audio_file)

        # Clean up
        os.unlink(temp_filename)
        return transcription.text
    except Exception as e:
        print(f"Error transcribing audio segment: {e}")
        raise TranscriptionError(
            f"Transcription failed after multiple retries: {e}"
        )  # Wrap in custom exception


@on_exception(expo, Exception, max_tries=MAX_RETRIES)
def analyze_transcript(transcript_text: str) -> str:
    """Analyze transcript using LLM with retry."""
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides concise summaries of YouTube video content.",
                },
                {
                    "role": "user",
                    "content": f"Please analyze and summarize the following transcript from a YouTube video: \n\n{transcript_text}",
                },
            ],
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty content received from analysis.")
        return content
    except Exception as e:
        print(f"Error analyzing transcript: {e}")
        raise AnalysisError(f"Analysis failed after multiple retries: {e}")


async def process_segment(
    youtube_url: str, start_seconds: int, end_seconds: int
) -> Optional[str]:
    """Process a single segment of the video asynchronously."""
    audio_buffer = download_youtube_audio_segment(
        youtube_url, start_seconds, end_seconds
    )
    if not audio_buffer:
        return None  # Handle download failure

    transcript = transcribe_audio_segment(audio_buffer)
    audio_buffer.close()  # Ensure buffer is closed
    if not transcript:
        return ""  # Handle transcription failure

    analysis = analyze_transcript(transcript)
    if not analysis:
        return ""  # Handle analysis failure
    return analysis


async def process_youtube_video_in_segments(
    youtube_url: str, segment_size_minutes: int = DEFAULT_SEGMENT_SIZE_MINUTES
) -> dict:
    """Process a YouTube video by downloading and processing segments asynchronously."""

    if not is_valid_youtube_url(youtube_url):
        raise ValueError("Invalid YouTube URL")

    # Convert minutes to seconds
    segment_size_seconds = segment_size_minutes * 60

    # Get video length
    video_length_seconds = get_video_length(youtube_url)
    if video_length_seconds == 0:
        raise ValueError("Failed to retrieve video length")

    # Calculate number of segments
    num_segments = math.ceil(video_length_seconds / segment_size_seconds)
    print(
        f"Video length: {video_length_seconds} seconds, will process in {num_segments} segments"
    )

    # Process each segment asynchronously
    tasks = []
    for i in range(num_segments):
        start_seconds = i * segment_size_seconds
        end_seconds = min((i + 1) * segment_size_seconds, video_length_seconds)
        print(
            f"Processing segment {i + 1}/{num_segments} ({start_seconds}-{end_seconds} seconds)"
        )
        tasks.append(process_segment(youtube_url, start_seconds, end_seconds))

    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)

    # Combine transcripts
    full_transcript = " ".join(results)

    # Analyze the combined transcript
    analysis = analyze_transcript(full_transcript)
    if not analysis:
        raise AnalysisError("Failed to analyze the full transcript")

    return {"transcript": full_transcript, "analysis": analysis}


def main():
    """Main function to run the script."""
    if not os.environ.get("GROQ_API_KEY"):
        print(
            "Error: GROQ_API_KEY environment variable not set. Please set it before running this script."
        )
        return

    youtube_url = input("Enter the YouTube video URL: ")
    segment_size_minutes = int(
        input(
            f"Enter segment size in minutes (default {DEFAULT_SEGMENT_SIZE_MINUTES}): "
        )
        or DEFAULT_SEGMENT_SIZE_MINUTES
    )

    start_time = time.time()
    result = asyncio.run(
        process_youtube_video_in_segments(youtube_url, segment_size_minutes)
    )
    end_time = time.time()

    if isinstance(result, str):  # Check for error message
        print(f"Error: {result}")
    else:
        print("Transcription and analysis complete!")
        print(f"Time taken: {end_time - start_time:.2f} seconds")
        print("\nTranscript:")
        print(result["transcript"])
        print("\nAnalysis:")
        print(result["analysis"])


if __name__ == "__main__":
    main()
