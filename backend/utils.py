"""
Utility helpers for the Automated Video Dubbing System.
Provides file handling, timestamp formatting, hashing, and job ID management.
"""

import json
import hashlib
import wave
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from backend.config import FFMPEG_PATH

def generate_job_id(url: str) -> str:
    """Generate a clean, deterministic 12-char job ID from a YouTube video ID or URL."""
    from backend.downloader import extract_youtube_id
    vid_id = extract_youtube_id(url)
    key = vid_id if vid_id else url.strip()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]

def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"

def format_duration(seconds: float) -> str:
    """Format duration into readable HH:MM:SS format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def save_json(data: Any, path: Path) -> None:
    """Safely write data to a JSON file with pretty formatting and UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(path: Path) -> Optional[Any]:
    """Safely load JSON from file if it exists, otherwise return None."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def is_valid_file(path: Path, min_size: int = 100) -> bool:
    """Check if file exists and has minimum valid content size."""
    return path.exists() and path.is_file() and path.stat().st_size >= min_size

def get_wav_duration(path: Path) -> float:
    """Return accurate duration of a WAV file in seconds."""
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        # Fallback to ffmpeg
        cmd = [
            FFMPEG_PATH, "-i", str(path), "-f", "null", "-"
        ]
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        # Parse Duration: 00:00:00.00
        for line in proc.stderr.splitlines():
            if "Duration:" in line:
                try:
                    time_str = line.split("Duration:")[1].split(",")[0].strip()
                    parts = time_str.split(":")
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                except Exception:
                    pass
        return 0.0
