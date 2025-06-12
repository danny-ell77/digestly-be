import re
from app.settings import settings
import yt_dlp
from app.logger import get_logger
from ..transcript_types import BaseTranscriptProcessor

logger = get_logger("transcript")


class YTDLPProcessor(BaseTranscriptProcessor):
    def __init__(self):
        proxy_username = settings.proxy_username
        proxy_password = settings.proxy_password

        proxy_url = f"http://{proxy_username}:{proxy_password}@p.webshare.io:80"
        self.ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "proxy": proxy_url,
        }

    def timestamp_to_seconds(self, timestamp):
        """Convert timestamp (HH:MM:SS.mmm or MM:SS.mmm) to seconds"""
        try:
            # Remove any extra formatting
            timestamp = timestamp.strip()

            # Handle different timestamp formats
            if timestamp.count(":") == 2:  # HH:MM:SS.mmm
                h, m, s = timestamp.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
            elif timestamp.count(":") == 1:  # MM:SS.mmm
                m, s = timestamp.split(":")
                return float(m) * 60 + float(s)
            else:  # Just seconds
                return float(timestamp)
        except ValueError:
            return 0.0

    def parse_vtt_content(self, content):
        """Parse VTT subtitle content"""
        lines = content.strip().split("\n")
        segments = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and WEBVTT header
            if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                i += 1
                continue

            # Check if this line contains a timestamp
            if "-->" in line:
                # Extract timestamp
                timestamp_match = re.match(r"(\d+:[\d:.]+)\s*-->\s*(\d+:[\d:.]+)", line)
                if timestamp_match:
                    start_time = self.timestamp_to_seconds(timestamp_match.group(1))
                    end_time = self.timestamp_to_seconds(timestamp_match.group(2))

                    # Collect text lines that follow
                    text_lines = []
                    i += 1
                    while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                        text = lines[i].strip()
                        # Remove HTML tags and formatting
                        text = re.sub(r"<[^>]*>", "", text)
                        text = re.sub(r"&[^;]+;", "", text)  # HTML entities
                        if text:
                            text_lines.append(text)
                        i += 1

                    if text_lines:
                        segments.append(
                            {
                                "start": start_time,
                                "end": end_time,
                                "text": " ".join(text_lines),
                            }
                        )
                else:
                    i += 1
            else:
                i += 1

        return segments

    def parse_srt_content(self, content):
        """Parse SRT subtitle content"""
        segments = []
        blocks = re.split(r"\n\s*\n", content.strip())

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                # Skip sequence number (first line)
                timestamp_line = lines[1]
                text_lines = lines[2:]

                # Parse timestamp
                timestamp_match = re.match(
                    r"(\d+:[\d:,]+)\s*-->\s*(\d+:[\d:,]+)", timestamp_line
                )
                if timestamp_match:
                    # Convert SRT timestamp format to VTT format
                    start_ts = timestamp_match.group(1).replace(",", ".")
                    end_ts = timestamp_match.group(2).replace(",", ".")

                    start_time = self.timestamp_to_seconds(start_ts)
                    end_time = self.timestamp_to_seconds(end_ts)

                    # Clean text
                    text = " ".join(text_lines)
                    text = re.sub(r"<[^>]*>", "", text)
                    text = re.sub(r"&[^;]+;", "", text)

                    if text.strip():
                        segments.append(
                            {"start": start_time, "end": end_time, "text": text.strip()}
                        )

        return segments

    def format_transcript_with_timestamps(
        self, segments, paragraph_timegap=30, sentence_endings=(".", "!", "?")
    ):
        """Format segments into paragraphs with timestamps"""
        if not segments:
            return ""

        formatted_segments = []
        current_paragraph = []
        last_timestamp = None

        for segment in segments:
            start_time = segment["start"]
            text = segment["text"]

            current_paragraph.append(text)

            is_sentence_end = text.rstrip().endswith(sentence_endings)
            time_gap = (
                (start_time - last_timestamp) > paragraph_timegap
                if last_timestamp
                else False
            )

            if is_sentence_end or time_gap:
                if current_paragraph:
                    paragraph_text = " ".join(current_paragraph)
                    formatted_segments.append(f"{paragraph_text} [[{start_time:.1f}]]")
                    current_paragraph = []

            last_timestamp = start_time

        if current_paragraph:
            paragraph_text = " ".join(current_paragraph)
            if segments:
                last_time = segments[-1]["start"]
                formatted_segments.append(f"{paragraph_text} [[{last_time:.1f}]]")
            else:
                formatted_segments.append(paragraph_text)

        return " ".join(formatted_segments)

    async def fetch_transcript(self, video_id, language_code="en"):
        """Extract transcript for a YouTube video"""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info.get("subtitles") and not info.get("automatic_captions"):
                    raise ValueError("No subtitles found for this video")

                subtitles = info.get("subtitles", {}).get("en", [])
                if not subtitles:
                    subtitles = info.get("automatic_captions", {}).get("en", [])

                if not subtitles:
                    raise ValueError("No English subtitles found")

                subtitle_info = None
                for sub in subtitles:
                    if sub.get("ext") == "vtt":
                        subtitle_info = sub
                        break

                if not subtitle_info:
                    subtitle_info = subtitles[0]

                subtitle_url = subtitle_info["url"]

                with yt_dlp.YoutubeDL(
                    {"quiet": True, "proxy": self.ydl_opts.get("proxy")}
                ) as ydl:
                    subtitle_data = ydl.urlopen(subtitle_url).read().decode("utf-8")

                # Parse based on format
                if subtitle_info.get("ext") == "vtt" or "WEBVTT" in subtitle_data:
                    segments = self.parse_vtt_content(subtitle_data)
                else:
                    segments = self.parse_srt_content(subtitle_data)

                if not segments:
                    raise ValueError("Could not parse subtitle content")

                transcript_text = self.format_transcript_with_timestamps(segments)

                logger.debug(
                    f"Successfully retrieved transcript with {len(segments)} segments"
                )
                return transcript_text

        except Exception as e:
            logger.error(f"yt-dlp error: {str(e)}")
            raise ValueError(f"Error retrieving transcript: {str(e)}")
