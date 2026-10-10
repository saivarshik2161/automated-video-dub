"""
Video Downloader module using yt-dlp.
Downloads YouTube videos reliably with format selection, caching, and progress tracking.
"""

import time
import re
import shutil
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, Callable
import yt_dlp

from backend.config import FFMPEG_PATH
from backend.utils import is_valid_file

def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extract the 11-character YouTube video ID from any valid YouTube URL format,
    including desktop, mobile, shorts, live, embed, and share links with extra query parameters.
    """
    if not url:
        return None
    url = url.strip()

    # Direct 11-character ID
    if re.match(r"^[0-9A-Za-z_-]{11}$", url):
        return url

    patterns = [
        r"(?:v=|vi=|\/v\/|embed\/|shorts\/|live\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"[?&]v=([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_valid_youtube_url(url: str) -> bool:
    """Validate if string contains a recognized YouTube video ID."""
    return extract_youtube_id(url) is not None

def download_video(
    url: str,
    job_dir: Path,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Tuple[Path, Dict[str, Any]]:
    """
    Download video from YouTube using yt-dlp.
    
    Args:
        url: YouTube video URL or ID.
        job_dir: Directory where job files are saved.
        on_progress: Optional callback reporting progress dict.
        
    Returns:
        Tuple of (source_video_path, video_metadata_dict)
    """
    video_id = extract_youtube_id(url)
    if not video_id:
        raise ValueError(
            f"Invalid YouTube URL: '{url}'. Please enter a valid YouTube video, shorts, or share link."
        )

    # Standardize to canonical URL to avoid query parameter anomalies
    clean_url = f"https://www.youtube.com/watch?v={video_id}"

    job_dir.mkdir(parents=True, exist_ok=True)
    target_video_path = job_dir / "source.mp4"

    # 1. Caching: Check if source video is already downloaded
    if is_valid_file(target_video_path, min_size=1024 * 50):
        if on_progress:
            on_progress({
                "stage": "download",
                "percent": 100,
                "message": "Using cached source video",
                "cached": True
            })
        return target_video_path, {"title": "Cached Video", "id": video_id}

    start_time = time.time()

    # Progress hook callback
    def progress_hook(d: Dict[str, Any]) -> None:
        if not on_progress:
            return

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = int((downloaded / total * 100)) if total > 0 else 0
            percent = min(max(percent, 0), 99)
            speed = d.get("speed") or 0
            speed_mb = speed / (1024 * 1024) if speed else 0.0

            on_progress({
                "stage": "download",
                "percent": percent,
                "message": f"Downloading video... {percent}% ({speed_mb:.1f} MB/s)",
                "elapsed": round(time.time() - start_time, 1)
            })
        elif status == "finished":
            on_progress({
                "stage": "download",
                "percent": 99,
                "message": "Download finished, finalizing video container...",
                "elapsed": round(time.time() - start_time, 1)
            })

    node_path = shutil.which("node")
    ydl_opts = {
        # Prioritize pre-merged single-stream formats (18=360p, 22=720p) for ultra-fast single request downloads
        "format": "18/22/best[height<=720][ext=mp4]/bestvideo[height<=720]+bestaudio/best",
        "outtmpl": str(job_dir / "source.%(ext)s"),
        "merge_output_format": "mp4",
        "ffmpeg_location": FFMPEG_PATH,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "overwrites": False,
        "continuedl": True,
        "retries": 20,
        "fragment_retries": 20,
        "file_access_retries": 10,
        "socket_timeout": 30,
        "retry_sleep_functions": {
            "http": lambda n: min(2 ** n, 10),
            "fragment": lambda n: min(2 ** n, 10),
            "file_access": lambda n: min(2 ** n, 10),
        },
        "concurrent_fragment_downloads": 2,
        "buffersize": 1024 * 512,
        "nocheckcertificate": True,
        "writesubtitles": True,
        "writeautomaticsub": False,
        "subtitleslangs": ["fr", "en"],
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web", "mweb", "tv"]
            }
        },
    }
    if node_path:
        ydl_opts["js_runtimes"] = {"node": {"path": node_path}}

    max_outer_attempts = 4
    last_error = None
    meta: Dict[str, Any] = {}

    for attempt in range(1, max_outer_attempts + 1):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if on_progress:
                    on_progress({
                        "stage": "download",
                        "percent": 0,
                        "message": "Fetching video information from YouTube..." if attempt == 1 else f"Resuming download (attempt {attempt}/{max_outer_attempts})...",
                        "elapsed": round(time.time() - start_time, 1)
                    })
                info = ydl.extract_info(clean_url, download=True)
                meta = {
                    "id": info.get("id", video_id),
                    "title": info.get("title", "Unknown Title"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown"),
                    "webpage_url": info.get("webpage_url", clean_url),
                    "thumbnail": info.get("thumbnail"),
                }
                break  # Successful download!
        except Exception as e:
            last_error = e
            if attempt < max_outer_attempts:
                wait_sec = 3 * attempt
                if on_progress:
                    on_progress({
                        "stage": "download",
                        "percent": 0,
                        "message": f"Network glitch detected. Auto-resuming in {wait_sec}s (attempt {attempt+1}/{max_outer_attempts})...",
                        "elapsed": round(time.time() - start_time, 1)
                    })
                time.sleep(wait_sec)
            else:
                raise RuntimeError(f"yt-dlp failed to download video after {max_outer_attempts} retries: {str(last_error)}") from last_error

    # Ensure source.mp4 exists (in case it saved as source.mkv or similar)
    if not target_video_path.exists():
        candidates = list(job_dir.glob("source.*"))
        if candidates:
            first_cand = candidates[0]
            if first_cand.suffix.lower() == ".mp4":
                target_video_path = first_cand
            else:
                first_cand.replace(target_video_path)

    if not is_valid_file(target_video_path):
        raise FileNotFoundError(f"Expected source video not found at {target_video_path}")

    clean_title = meta.get("title", "Video")
    if len(clean_title) > 60:
        clean_title = clean_title[:57] + "..."

    if on_progress:
        on_progress({
            "stage": "download",
            "percent": 100,
            "message": f"Downloaded: {clean_title}",
            "elapsed": round(time.time() - start_time, 1)
        })

    return target_video_path, meta
