"""
Video Processor module using FFmpeg.
Combines original video stream with synthesized English audio track,
optimizing with stream copying (-c:v copy) and web-streaming flags (-movflags +faststart).
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from backend.config import FFMPEG_PATH
from backend.utils import is_valid_file

def inspect_video_clock(video_path: Path) -> Dict[str, Any]:
    """
    Inspect the video stream, container duration, framerate, and PTS clock structure
    using PyAV in-process.
    """
    try:
        import av
        with av.open(str(video_path)) as container:
            video_stream = next((s for s in container.streams if s.type == 'video'), None)
            audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
            
            fps = float(video_stream.average_rate) if video_stream and video_stream.average_rate else 30.0
            duration = float(container.duration / av.time_base) if container.duration else 0.0
            
            return {
                "duration_seconds": round(duration, 3),
                "fps": round(fps, 3),
                "has_video": video_stream is not None,
                "has_audio": audio_stream is not None,
                "video_codec": video_stream.codec_context.name if video_stream else "unknown",
                "width": video_stream.codec_context.width if video_stream else 0,
                "height": video_stream.codec_context.height if video_stream else 0,
                "time_base": str(video_stream.time_base) if video_stream else ""
            }
    except Exception as e:
        return {"error": str(e), "fps": 30.0}

def merge_video_and_audio(
    video_path: Path,
    audio_path: Path,
    output_mp4_path: Path,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Path:
    """
    Multiplex original video stream with the newly aligned English audio track.
    Avoids video re-encoding by stream copying (-c:v copy).
    
    Args:
        video_path: Path to source video.
        audio_path: Path to aligned WAV audio.
        output_mp4_path: Target path for final_dubbed.mp4.
        on_progress: Optional progress callback.
        
    Returns:
        Path to final dubbed MP4.
    """
    output_mp4_path.parent.mkdir(parents=True, exist_ok=True)

    # Caching check
    if is_valid_file(output_mp4_path, min_size=1024 * 50):
        if on_progress:
            on_progress({
                "stage": "remix",
                "percent": 100,
                "message": "Using cached final dubbed video",
                "cached": True
            })
        return output_mp4_path

    start_time = time.time()
    if on_progress:
        on_progress({
            "stage": "remix",
            "percent": 20,
            "message": "Remuxing video with new English audio (stream copy)...",
            "elapsed": 0.0
        })

    # Primary command: stream copy video track without lossy re-encoding, locking PTS to 0
    cmd_copy = [
        FFMPEG_PATH,
        "-y",
        "-avoid_negative_ts", "make_zero",
        "-fflags", "+genpts",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-movflags", "+faststart",
        str(output_mp4_path)
    ]

    result = subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # If stream copy fails (e.g. video container incompatibility), fallback to re-encoding video
    if result.returncode != 0:
        if on_progress:
            on_progress({
                "stage": "remix",
                "percent": 40,
                "message": "Stream copy incompatible, re-encoding video stream to H.264...",
                "elapsed": round(time.time() - start_time, 1)
            })

        cmd_reencode = [
            FFMPEG_PATH,
            "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            "-movflags", "+faststart",
            str(output_mp4_path)
        ]
        result = subprocess.run(cmd_reencode, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed to merge video and audio:\n{result.stderr[-500:]}"
            )

    if not is_valid_file(output_mp4_path):
        raise FileNotFoundError(f"Final dubbed video was not created at {output_mp4_path}")

    if on_progress:
        on_progress({
            "stage": "remix",
            "percent": 100,
            "message": "Final dubbed video created successfully",
            "elapsed": round(time.time() - start_time, 1)
        })

    return output_mp4_path
