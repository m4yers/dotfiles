#!/usr/bin/env python3
"""Fetch a YouTube video transcript and print it as plain text."""
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: fetch-transcript VIDEO_ID", file=sys.stderr)
        sys.exit(1)

    video_id = sys.argv[1]

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id=video_id)
        for entry in transcript:
            print(entry.text)
    except Exception as e:
        print(f"Error fetching transcript: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
