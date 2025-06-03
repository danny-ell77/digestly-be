import subprocess
from pathlib import Path
import yt_dlp
from groq import Groq
import os
from premium import TranscriptionError


def download_video(video_url: str, save_path: Path) -> Path:
    """Download video using yt-dlp."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    ydl_opts = {
        "outtmpl": str(save_path.with_suffix(".mp4")),
        "format": "mp4",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return save_path.with_suffix(".mp4")


def extract_audio(video_path: Path) -> Path:
    """Extract audio from video using ffmpeg, but only if audio stream exists."""
    audio_path = video_path.with_suffix(".wav")

    # Use ffprobe to check for audio streams
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=nw=1:nk=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        if not probe.stdout.strip():
            raise ValueError("No audio stream found in the video.")

        # Proceed with audio extraction if audio stream exists
        command = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(audio_path),
        ]
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return audio_path

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe error: {e.stderr}") from e
    except Exception as e:
        raise RuntimeError(f"Audio extraction failed: {e}") from e


def transcribe_audio(audio_path: Path) -> str:
    """Transcribe an audio segment with retry."""
    with open(audio_path, "rb") as audio_file:
        try:
            import asyncio

            client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
            transcription = asyncio.wait_for(
                client.audio.transcriptions.create(
                    file=audio_file,
                    model="distil-whisper-large-v3-en",
                    language="en",
                    temperature=0.0,
                    max_retries=3,
                ),
                timeout=30.0,
            )
            if not transcription.text:
                raise ValueError("Transcription returned empty text.")
            return transcription.text
        except Exception as e:
            print(f"Error transcribing audio segment: {e}")
            raise TranscriptionError(
                f"Transcription failed after multiple retries: {e}"
            )  # Wrap in custom exception


def process_youtube_video(video_url: str, output_dir: Path = Path("output")) -> str:
    """Process a YouTube video: download, extract audio, and transcribe."""
    try:
        # Step 1: Download the video
        video_path = download_video(video_url, output_dir / "video")

        # Step 2: Extract audio from the video
        audio_path = extract_audio(video_path)

        # Step 3: Transcribe the audio
        transcription = transcribe_audio(audio_path)

        return transcription
    except Exception as e:
        print(f"Error processing YouTube video: {e}")
        raise
