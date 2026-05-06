---
name: youtube-summariser
type: tool
description: Fetch YouTube video transcripts and summarise them. Use when user says "summarise youtube", "youtube summary", "transcript of youtube", "summarise video", or provides a YouTube URL to summarise.
---

# YouTube Summariser

Fetch a YouTube video transcript and produce a structured summary organised
by topics with bullet points.

## Parameters

- **url** (required): YouTube URL or bare 11-character video ID

## Dependencies

- `tiling` — pane layout
- `editor` — show summary file

## Steps

1. Set up environment, log activation, and build the tiling layout:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/skill-analytics/scripts/add-invocation.sh \
     youtube-summariser user:summarise
   $SKILLS/tiling/scripts/run-ttm.sh activity set \
     "youtube-summariser: fetching transcript"
   eval "$($SKILLS/tiling/scripts/run-ttm.sh layout build)"
   ```
2. Extract the video ID from the URL or bare ID:
   ```bash
   VIDEO_ID=$(python3 $SKILLS/youtube-summariser/scripts/parse-video-id.py \
     "URL_OR_ID")
   ```
3. Fetch the transcript:
   ```bash
   $SKILLS/youtube-summariser/scripts/fetch-transcript.sh "$VIDEO_ID"
   ```
   The script prints the plain-text transcript to stdout. If the video
   has no captions, it exits with code 1 and prints an error message.
4. Produce a summary from the transcript and write it to
   `/tmp/yt-summary-VIDEO_ID.md` with this structure:
   ```
   # Video Title (if known) — Summary

   ## Topic Name
   - Key point
   - Key point

   ## Topic Name
   - Key point
   ```
5. Show the summary in the editor:
   ```bash
   $SKILLS/editor/scripts/run-editor.sh show only \
     /tmp/yt-summary-VIDEO_ID.md
   $SKILLS/tiling/scripts/run-ttm.sh activity set \
     "youtube-summariser: done"
   ```

## Rules

- Use the fetch-transcript script to get the transcript — direct web
  fetching of YouTube pages does not return transcript data.
- Extract the video ID before calling the script; it expects a bare
  video ID, not a URL.
- Organise the summary by topics, not chronologically — topic grouping
  is more useful for reference.
- Include 3–8 bullet points per topic.
- Keep the total summary under 2 pages of text unless the user asks
  for more detail.
- Ground all summary points in the transcript text because unsupported
  claims mislead the user.
- Note the speaker or course name if identifiable from the transcript.

## Completion

| Status               | Criteria                                    |
|----------------------|---------------------------------------------|
| `DONE`               | Summary written and shown in editor         |
| `DONE_WITH_CONCERNS` | Transcript partial or auto-generated        |
|                      | captions with quality issues                |
| `BLOCKED`            | No captions available for the video         |
| `NEEDS_CONTEXT`      | YouTube URL or video ID not provided        |

- Stop after 3 failed attempts to fetch the transcript and report
  status BLOCKED with what was tried.
