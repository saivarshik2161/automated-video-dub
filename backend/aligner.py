"""
Timing and Alignment module.
Synchronizes synthesized speech with original video timing using tempo scaling (atempo)
and sample-accurate timeline construction.
"""

import time
import wave
import numpy as np
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any

from backend.models import SynthesizedSegment
from backend.audio_processor import time_stretch_audio
from backend.utils import get_wav_duration, is_valid_file

def align_audio(
    synthesized_segments: List[SynthesizedSegment],
    total_duration: float,
    output_aligned_path: Path,
    speed_adjustment: bool = True,
    sample_rate: int = 24000,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Path:
    """
    Align all synthesized segments onto a master audio timeline matching original video duration.
    
    Args:
        synthesized_segments: List of synthesized segments with audio files.
        total_duration: Total duration of the original video/audio in seconds.
        output_aligned_path: Path where aligned_audio.wav will be written.
        speed_adjustment: Whether to time-stretch speech that exceeds original segment length.
        sample_rate: Target sample rate for alignment (default 24000Hz).
        on_progress: Optional progress callback.
        
    Returns:
        Path to the aligned master WAV file.
    """
    output_aligned_path.parent.mkdir(parents=True, exist_ok=True)

    # Caching check
    if is_valid_file(output_aligned_path, min_size=1024):
        if on_progress:
            on_progress({
                "stage": "align",
                "percent": 100,
                "message": "Using cached aligned audio",
                "cached": True
            })
        return output_aligned_path

    start_time = time.time()
    total_segments = len(synthesized_segments)

    # 1. Initialize master audio buffer with silence (zeros) matching video duration
    total_samples = int(total_duration * sample_rate) + (sample_rate * 2)  # 2s safety buffer
    master_timeline = np.zeros(total_samples, dtype=np.int16)

    stretched_dir = output_aligned_path.parent / "stretched"
    if speed_adjustment:
        stretched_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: List[Dict[str, Any]] = []

    for i, seg in enumerate(synthesized_segments):
        if not seg.audio_path or not Path(seg.audio_path).exists():
            continue

        orig_start = float(seg.start)
        orig_end = float(seg.end)
        source_dur = max(orig_end - orig_start, 0.2)
        raw_dur = float(seg.audio_duration)

        # Lookahead: determine maximum window before the next speaker speaks
        if i < total_segments - 1:
            next_start = float(synthesized_segments[i + 1].start)
            # Leave a 50ms buffer before the next speaker starts
            allowed_window = max(source_dur, next_start - orig_start - 0.05)
        else:
            allowed_window = max(source_dur, total_duration - orig_start - 0.05)

        audio_file_to_place = Path(seg.audio_path)
        actual_speed_factor = 1.0

        # 2. Independent segment tempo scaling: fit audio within its allocated time window
        if speed_adjustment and raw_dur > source_dur:
            # First attempt: scale to fit within source_dur if possible, or allowed_window
            target_time = source_dur if (raw_dur / source_dur) <= 1.60 else min(allowed_window, source_dur * 1.35)
            if target_time > 0 and raw_dur > target_time:
                speed_ratio = raw_dur / target_time
                actual_speed_factor = min(max(speed_ratio, 1.0), 1.65)
                stretched_file = stretched_dir / f"stretched_{seg.index:04d}.wav"
                time_stretch_audio(
                    input_wav=Path(seg.audio_path),
                    output_wav=stretched_file,
                    speed_factor=actual_speed_factor
                )
                audio_file_to_place = stretched_file

        # 3. Read PCM samples and place onto master timeline at EXACT source_start
        try:
            with wave.open(str(audio_file_to_place), "rb") as wf:
                n_frames = wf.getnframes()
                audio_bytes = wf.readframes(n_frames)
                seg_samples = np.frombuffer(audio_bytes, dtype=np.int16)

            # Strictly place at absolute master timestamp: zero cumulative drift!
            start_sample = int(round(orig_start * sample_rate))
            max_allowed_samples = int(round(allowed_window * sample_rate))

            # Cap samples strictly before next speaker starts with a smooth 15ms micro-fade
            if len(seg_samples) > max_allowed_samples:
                seg_samples = seg_samples[:max_allowed_samples].copy()
                fade_n = min(len(seg_samples), int(0.015 * sample_rate))
                if fade_n > 0:
                    fade_curve = np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
                    seg_samples[-fade_n:] = (seg_samples[-fade_n:].astype(np.float32) * fade_curve).astype(np.int16)

            end_sample = start_sample + len(seg_samples)

            if end_sample > len(master_timeline):
                pad_size = end_sample - len(master_timeline)
                master_timeline = np.pad(master_timeline, (0, pad_size), mode="constant")

            # Place dialogue onto absolute master timeline
            master_timeline[start_sample:end_sample] = seg_samples

            placed_duration = float(len(seg_samples)) / sample_rate
            dub_end = orig_start + placed_duration

            manifest_entries.append({
                "index": seg.index,
                "speaker": seg.speaker,
                "voice": seg.voice,
                "source_start": round(orig_start, 3),
                "source_end": round(orig_end, 3),
                "source_duration": round(source_dur, 3),
                "english_text": seg.text,
                "raw_audio_duration": round(raw_dur, 3),
                "speed_factor": round(actual_speed_factor, 3),
                "dub_start": round(orig_start, 3),
                "dub_end": round(dub_end, 3),
                "dub_duration": round(placed_duration, 3),
                "onset_drift_seconds": 0.000,
                "stops_before_next_speaker": (i == total_segments - 1) or (dub_end <= synthesized_segments[i + 1].start)
            })

        except Exception as e:
            pass

        if on_progress:
            pct = int(((i + 1) / max(total_segments, 1)) * 95)
            on_progress({
                "stage": "align",
                "percent": pct,
                "message": f"Aligning master timeline: segment [{i+1}/{total_segments}]...",
                "elapsed": round(time.time() - start_time, 1)
            })

    # 4. Save per-segment alignment manifest
    manifest_path = output_aligned_path.parent / "alignment_manifest.json"
    try:
        import json
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump({
                "total_segments": len(manifest_entries),
                "master_clock": "ORIGINAL_VIDEO_TIMELINE",
                "cumulative_drift_seconds": 0.000,
                "segments": manifest_entries
            }, mf, indent=2, ensure_ascii=False)
    except Exception:
        pass

    # 5. Write final master WAV matching exact source video duration
    target_samples = int(round(total_duration * sample_rate))
    if len(master_timeline) < target_samples:
        final_buffer = np.pad(master_timeline, (0, target_samples - len(master_timeline)), mode="constant")
    else:
        final_buffer = master_timeline[:target_samples]

    with wave.open(str(output_aligned_path), "wb") as out_wf:
        out_wf.setnchannels(1)
        out_wf.setsampwidth(2)  # 16-bit PCM
        out_wf.setframerate(sample_rate)
        out_wf.writeframes(final_buffer.tobytes())

    if on_progress:
        on_progress({
            "stage": "align",
            "percent": 100,
            "message": f"Audio aligned successfully: {get_wav_duration(output_aligned_path):.1f}s master timeline",
            "elapsed": round(time.time() - start_time, 1)
        })

    return output_aligned_path
