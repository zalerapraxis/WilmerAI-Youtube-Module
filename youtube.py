import re
import os
import tempfile
import subprocess
import requests
from typing import List, Tuple, Optional

import json

def get_video_title_and_channel(url: str):
    """
    Fetches the video title and channel name using YouTube's oEmbed API.
    Returns (title, channel) or ("Unknown Title", "Unknown Channel") on failure.
    """
    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
    try:
        resp = requests.get(oembed_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        title = data.get("title", "Unknown Title")
        channel = data.get("author_name", "Unknown Channel")
        return title, channel
    except Exception:
        return "Unknown Title", "Unknown Channel"

def extract_video_id(input_text: str) -> Optional[str]:
    print("Extract the YouTube video ID from a potentially unsanitized input.")
    # Remove any leading or trailing whitespace
    input_text = input_text.strip()
    
    # Extract the URL from the input text
    url_match = re.search(r'https?://[^\s]+', input_text)
    if url_match:
        url = url_match.group(0)
    else:
        return None
    
    # Define patterns to match YouTube URLs
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[&?\/]|$)',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    
    # Search for a YouTube URL in the extracted URL
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_sponsor_segments(video_id: str) -> List[Tuple[float, float]]:
    print("Query SponsorBlock API for sponsor segments.")
    api_url = f'https://sponsor.ajay.app/api/skipSegments?videoID={video_id}'
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        segments = []
        for entry in data:
            for seg in entry.get('segments', []):
                start, end = seg
                segments.append((float(start), float(end)))
        return segments
    except Exception:
        return []

def download_subtitles(url: str, out_dir: str) -> Optional[str]:
    print("Download subtitles using yt-dlp. Returns path to subtitle file or None.")
    # Try VTT first, then SRT
    for ext in ['vtt', 'srt']:
        out_path = os.path.join(out_dir, f'subs.{ext}')
        cmd = [
            'yt-dlp',
            '--write-auto-sub',
            '--sub-lang', 'en',
            '--skip-download',
            '--sub-format', ext,
            '-o', out_path,
            url
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # yt-dlp outputs as subs.ext, but may append .en or .en-US
            for fname in os.listdir(out_dir):
                if fname.startswith('subs') and fname.endswith(f'.{ext}'):
                    return os.path.join(out_dir, fname)
        except Exception:
            continue
    return None

def parse_vtt(path: str) -> List[Tuple[float, float, str]]:
    print("Parse WebVTT file and return list of (start, end, text) cues.")
    cues = []
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '-->' in line:
            times = line.split('-->')
            start = vtt_time_to_seconds(times[0].strip())
            end = vtt_time_to_seconds(times[1].strip())
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                text_lines.append(lines[i].strip())
                i += 1
            text = ' '.join(text_lines).strip()
            if text:
                cues.append((start, end, text))
        i += 1
    return cues

def vtt_time_to_seconds(t: str) -> float:
    # Format: HH:MM:SS.mmm or MM:SS.mmm
    parts = t.split(':')
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        return 0.0
    s, *ms = s.split('.')
    ms = ms[0] if ms else '0'
    total = int(h) * 3600 + int(m) * 60 + int(s) + float(f'0.{ms}')
    return total

def parse_srt(path: str) -> List[Tuple[float, float, str]]:
    print("Parse SRT file and return list of (start, end, text) cues.")
    cues = []
    with open(path, encoding='utf-8') as f:
        content = f.read()
    blocks = re.split(r'\\n\\s*\\n', content)
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) >= 2:
            # First line: index, Second line: time, Rest: text
            time_line = lines[1]
            match = re.match(r'(\\d{2}:\\d{2}:\\d{2},\\d{3})\\s*-->\\s*(\\d{2}:\\d{2}:\\d{2},\\d{3})', time_line)
            if match:
                start = srt_time_to_seconds(match.group(1))
                end = srt_time_to_seconds(match.group(2))
                text = ' '.join(l.strip() for l in lines[2:] if l.strip())
                if text:
                    cues.append((start, end, text))
    return cues

def srt_time_to_seconds(t: str) -> float:
    print("Format: HH:MM:SS,mmm")
    # Format: HH:MM:SS,mmm
    h, m, s_ms = t.split(':')
    s, ms = s_ms.split(',')
    total = int(h) * 3600 + int(m) * 60 + int(s) + float(f'0.{ms}')
    return total

def cues_overlap(cue_start: float, cue_end: float, segments: List[Tuple[float, float]]) -> bool:
    for seg_start, seg_end in segments:
        if cue_end > seg_start and cue_start < seg_end:
            return True
    return False

def deduplicate_cues(cues: List[Tuple[float, float, str]]) -> List[str]:
    """
    Deduplicate overlapping/consecutive fragments using a sliding window,
    stripping tags and HTML entities before deduplication.
    """
    deduped = []
    prev = ""
    for _, _, text in cues:
        # Remove tags
        cue_text = re.sub(r"<[^>]+>", "", text)
        # Remove HTML entities
        cue_text = re.sub(r"&[a-zA-Z]+;", "", cue_text)
        # Remove extra whitespace
        cue_text = " ".join(cue_text.strip().split())
        if not cue_text:
            continue
        # Sliding window overlap removal
        overlap = 0
        max_overlap = min(len(prev), len(cue_text))
        for i in range(max_overlap, 0, -1):
            if prev[-i:] == cue_text[:i]:
                overlap = i
                break
        deduped.append(cue_text[overlap:] if overlap else cue_text)
        prev = cue_text
    return [t for t in deduped if t]

def extract_transcript(url: str) -> str:
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError('Could not extract video ID from URL')
    sponsor_segments = get_sponsor_segments(video_id)
    # Construct the YouTube URL from the video_id
    constructed_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Fetch title and channel using the constructed URL
    title, channel = get_video_title_and_channel(constructed_url)
    with tempfile.TemporaryDirectory() as tmpdir:
        sub_path = download_subtitles(constructed_url, tmpdir)
        if not sub_path:
            raise RuntimeError('Could not download subtitles')
        if sub_path.endswith('.vtt'):
            cues = parse_vtt(sub_path)
        elif sub_path.endswith('.srt'):
            cues = parse_srt(sub_path)
        else:
            raise RuntimeError('Unknown subtitle format')
        # Filter out sponsor cues
        filtered = [
            (start, end, text)
            for (start, end, text) in cues
            if not cues_overlap(start, end, sponsor_segments)
        ]
        deduped = deduplicate_cues(filtered)
        # Remove all <...> tags and HTML entities from each line, collapse whitespace, and join into a single string
        cleaned = []
        for line in deduped:
            # Remove tags
            line = re.sub(r"<[^>]+>", "", line)
            # Remove HTML entities
            line = re.sub(r"&[a-zA-Z]+;", "", line)
            # Collapse whitespace
            line = " ".join(line.strip().split())
            if line:
                cleaned.append(line)
        transcript = " ".join(cleaned)
        prefix = f"{title} by {channel}:\n\n"
        return prefix + transcript.strip()

def Invoke(*args, **kwargs):
    print(f"Entrypoint: Invoke({args}) -> transcript string")
    if args:
        url = args[0]
    else:
        url = kwargs.get('url')
    if not url:
        raise ValueError('You must provide a YouTube URL')
    return extract_transcript(url)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(Invoke(url))
    else:
        print("Please provide a YouTube URL as a command line argument.")