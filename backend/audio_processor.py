"""
Audio Processor module using FFmpeg.
Handles audio extraction, time-stretching (atempo), format conversion, and duration inspection.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from backend.config import FFMPEG_PATH
from backend.utils import is_valid_file, get_wav_duration

def extract_audio(
    video_path: Path,
    output_audio_path: Path,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Path:
    """
    Extract 16kHz mono 16-bit PCM WAV from source video using FFmpeg.
    Ideal for Whisper transcription.
    """
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)

    # Caching check
    if is_valid_file(output_audio_path, min_size=1024):
        if on_progress:
            on_progress({
                "stage": "extract_audio",
                "percent": 100,
                "message": "Using cached extracted audio",
                "cached": True
            })
        return output_audio_path

    start_time = time.time()
    if on_progress:
        on_progress({
            "stage": "extract_audio",
            "percent": 10,
            "message": "Extracting audio with FFmpeg...",
            "elapsed": 0.0
        })

    # FFmpeg command: extract audio to 16kHz mono PCM WAV
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_audio_path)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg audio extraction failed (code {result.returncode}):\n{result.stderr[-500:]}"
        )

    if not is_valid_file(output_audio_path):
        raise FileNotFoundError(f"Failed to generate extracted audio at {output_audio_path}")

    if on_progress:
        on_progress({
            "stage": "extract_audio",
            "percent": 100,
            "message": "Source audio extracted successfully (16kHz PCM WAV)",
            "elapsed": round(time.time() - start_time, 1)
        })

    return output_audio_path

def build_atempo_filter(speed_factor: float) -> str:
    """
    Build FFmpeg atempo filter string.
    Since atempo only supports factors between 0.5 and 2.0, chain filters if needed.
    """
    filters = []
    factor = speed_factor

    while factor > 2.0:
        filters.append("atempo=2.0")
        factor /= 2.0
    while factor < 0.5:
        filters.append("atempo=0.5")
        factor /= 0.5

    filters.append(f"atempo={factor:.4f}")
    return ",".join(filters)

def time_stretch_audio(
    input_wav: Path,
    output_wav: Path,
    speed_factor: float,
    min_speed: float = 1.0,
    max_speed: float = 1.60
) -> Path:
    """
    Time-stretch audio using FFmpeg's atempo filter to change speed while preserving pitch.
    Clamps factor strictly between 0.95 and 1.25 to preserve natural intelligibility without robotic/chipmunk extremes.
    """
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    # Clamping speed factor to avoid robotic chipmunk or sluggish drone
    clamped_speed = max(min_speed, min(speed_factor, max_speed))

    if abs(clamped_speed - 1.0) < 0.02:
        # If speed is virtually 1.0, just copy or return original
        if input_wav != output_wav:
            import shutil
            shutil.copy2(input_wav, output_wav)
        return output_wav

    filter_str = build_atempo_filter(clamped_speed)
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_wav),
        "-filter:a", filter_str,
        "-acodec", "pcm_s16le",
        "-ar", "24000",
        "-ac", "1",
        str(output_wav)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg time-stretching failed (code {result.returncode}):\n{result.stderr[-400:]}"
        )

    return output_wav

def convert_to_wav(input_audio: Path, output_wav: Path, sample_rate: int = 24000) -> Path:
    """Convert any audio file (e.g. Edge-TTS MP3) to standard mono WAV."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(input_audio),
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output_wav)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg conversion to WAV failed:\n{result.stderr[-400:]}")
    return output_wav

def generate_silence(output_wav: Path, duration: float = 1.0, sample_rate: int = 24000) -> Path:
    """Generate a clean PCM silence WAV file with the given duration."""
    import wave
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    n_samples = max(1, int(max(0.1, duration) * sample_rate))
    with wave.open(str(output_wav), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * n_samples)
    return output_wav

def trim_silence_from_wav(
    wav_path: Path,
    threshold: int = 250,
    pad_ms: int = 12,
    fade_ms: int = 8
) -> float:
    """
    Trim leading and trailing silence/encoder dead air from a WAV file.
    Edge-TTS and MP3 decoders introduce 180-230ms of leading silence and ~1.0s of trailing silence.
    Stripping this ensures spoken English dialogue begins at the exact millisecond of the video timestamp,
    preventing any perceived speech lag or artificial duration bloat.
    
    Applies a smooth micro-fade at boundaries to eliminate clicks.
    Returns the new trimmed duration in seconds.
    """
    import wave
    import numpy as np

    if not wav_path.exists() or wav_path.stat().st_size < 100:
        return 0.0

    try:
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            frames = wf.readframes(n_frames)

        if n_frames == 0 or sampwidth != 2:
            return float(n_frames) / max(framerate, 1)

        samples = np.frombuffer(frames, dtype=np.int16)
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels)[:, 0]

        abs_samples = np.abs(samples)
        peak = int(np.max(abs_samples)) if len(abs_samples) > 0 else 0
        if peak < threshold:
            # Entirely silence, return current duration
            return float(n_frames) / framerate

        effective_thresh = max(threshold, int(peak * 0.02))
        speech_indices = np.where(abs_samples > effective_thresh)[0]
        if len(speech_indices) == 0:
            return float(n_frames) / framerate

        first_speech = speech_indices[0]
        last_speech = speech_indices[-1]

        pad_samples = int((pad_ms / 1000.0) * framerate)
        start_idx = max(0, first_speech - pad_samples)
        end_idx = min(len(samples), last_speech + pad_samples)

        trimmed = samples[start_idx:end_idx].copy()
        if len(trimmed) == 0:
            return float(n_frames) / framerate

        # Apply micro-fade in / micro-fade out
        fade_samples = min(len(trimmed) // 4, int((fade_ms / 1000.0) * framerate))
        if fade_samples > 0:
            fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
            trimmed[:fade_samples] = (trimmed[:fade_samples].astype(np.float32) * fade_in).astype(np.int16)
            fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
            trimmed[-fade_samples:] = (trimmed[-fade_samples:].astype(np.float32) * fade_out).astype(np.int16)

        with wave.open(str(wav_path), "wb") as out_wf:
            out_wf.setnchannels(1)
            out_wf.setsampwidth(2)
            out_wf.setframerate(framerate)
            out_wf.writeframes(trimmed.tobytes())

        return float(len(trimmed)) / framerate
    except Exception:
        return get_wav_duration(wav_path)


