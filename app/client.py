import argparse
import requests
import json
import sys


def get_transcript(api_url, video_id, language_code=None):
    """Get transcript from API"""
    payload = {"video_id": video_id}

    if language_code:
        payload["language_code"] = language_code

    response = requests.post(f"{api_url}/transcript/", json=payload)

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        sys.exit(1)

    return response.json()


def process_with_ai(api_url, video_id, mode, language_code=None, prompt_template=None):
    """Process video with Claude/Ollama"""
    payload = {"video_id": video_id, "mode": mode}

    if language_code:
        payload["language_code"] = language_code

    if prompt_template:
        payload["prompt_template"] = prompt_template

    response = requests.post(f"{api_url}/process/", json=payload)

    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        sys.exit(1)

    return response.json()


def main():
    parser = argparse.ArgumentParser(
        description="Client for YouTube Transcript Processor API"
    )
    parser.add_argument("--api-url", default="http://localhost:8000", help="API URL")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Transcript command
    transcript_parser = subparsers.add_parser("transcript", help="Get video transcript")
    transcript_parser.add_argument("video_id", help="YouTube video ID or URL")
    transcript_parser.add_argument(
        "--language", help="Language code (e.g., 'en')", default="en"
    )
    transcript_parser.add_argument("--output", help="Output file (default: stdout)")

    # Process command
    process_parser = subparsers.add_parser("process", help="Process video with Claude")
    process_parser.add_argument("video_id", help="YouTube video ID or URL")
    process_parser.add_argument(
        "--mode",
        choices=["comprehensive", "tldr", "key_insights"],
        default="comprehensive",
        help="Processing mode: comprehensive (detailed summary), tldr (brief summary), or key_insights (bullet points)",
    )
    process_parser.add_argument(
        "--language", help="Language code (e.g., 'en')", default="en"
    )
    process_parser.add_argument("--prompt", help="Custom prompt template")
    process_parser.add_argument("--output", help="Output file (default: stdout)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "transcript":
        result = get_transcript(args.api_url, args.video_id, args.language)
        output = json.dumps(result, indent=2)
    elif args.command == "process":
        result = process_with_ai(
            args.api_url, args.video_id, args.mode, args.language, args.prompt
        )
        output = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
