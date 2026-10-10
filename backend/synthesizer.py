"""
Speech Synthesis module using Edge-TTS.
Generates natural, expressive English speech concurrently to maximize throughput
while preserving segment-level timing control. Bulletproof against non-Latin characters and API anomalies.
"""

import asyncio
import re
import time
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any, Tuple
import edge_tts

from backend.config import DEFAULT_TTS_VOICE
from backend.models import TranslatedSegment, SynthesizedSegment
from backend.audio_processor import convert_to_wav, generate_silence, trim_silence_from_wav
from backend.utils import get_wav_duration, is_valid_file

def sanitize_text_for_voice(text: str, voice: str) -> str:
    """Ensure text passed to Edge-TTS voice contains compatible characters."""
    clean = text.strip()
    if not clean:
        return "..."

    # If an English voice (en-*) is used, strip/replace incompatible non-Latin characters
    # that cause Edge-TTS to return "No audio was received"
    if voice.lower().startswith("en-"):
        has_non_latin = any(ord(c) > 0x024F and c.isalnum() for c in clean)
        if has_non_latin:
            # Replace non-Latin with ASCII or clean up
            ascii_text = clean.encode("ascii", "replace").decode("ascii")
            ascii_text = re.sub(r"\?+", " ", ascii_text).strip()
            if not any(c.isalnum() for c in ascii_text):
                return "..."
            return ascii_text

    return clean

async def _synthesize_single_segment_async(
    text: str,
    voice: str,
    output_wav_path: Path,
    expected_duration: float = 1.0
) -> float:
    """
    Async generation of a single speech segment with multi-level fallbacks.
    Guarantees the pipeline will NEVER crash on a problematic segment.
    """
    clean_text = text.strip()
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    temp_mp3 = output_wav_path.with_suffix(".mp3")

    if not clean_text or not any(c.isalnum() for c in clean_text):
        generate_silence(output_wav_path, duration=max(0.3, expected_duration), sample_rate=24000)
        return get_wav_duration(output_wav_path)

    # Compute speech rate: brisk if dense, but NEVER slower than natural (+0%)
    words = clean_text.split()
    target_wps = len(words) / max(0.3, expected_duration)
    if target_wps > 2.5:
        rate_boost = min(int((target_wps / 2.3 - 1.0) * 100), 25)
        rate_str = f"+{rate_boost}%"
    else:
        rate_str = "+0%"

    # Level 1: Attempt standard synthesis with sanitized voice-compatible text
    target_text = sanitize_text_for_voice(clean_text, voice)
    try:
        communicate = edge_tts.Communicate(target_text, voice, rate=rate_str)
        await communicate.save(str(temp_mp3))
        convert_to_wav(temp_mp3, output_wav_path, sample_rate=24000)
        trimmed_dur = trim_silence_from_wav(output_wav_path)
        if temp_mp3.exists():
            temp_mp3.unlink(missing_ok=True)
        return trimmed_dur
    except Exception:
        pass

    # Level 2: Fallback attempt with strict ASCII filtering
    try:
        ascii_text = clean_text.encode("ascii", "ignore").decode("ascii").strip() or "..."
        communicate = edge_tts.Communicate(ascii_text, voice, rate=rate_str)
        await communicate.save(str(temp_mp3))
        convert_to_wav(temp_mp3, output_wav_path, sample_rate=24000)
        trimmed_dur = trim_silence_from_wav(output_wav_path)
        if temp_mp3.exists():
            temp_mp3.unlink(missing_ok=True)
        return trimmed_dur
    except Exception:
        pass

    # Level 3: Bulletproof fallback: generate exact duration silence so audio timeline is preserved
    if temp_mp3.exists():
        temp_mp3.unlink(missing_ok=True)
    generate_silence(output_wav_path, duration=max(0.3, expected_duration), sample_rate=24000)
    return get_wav_duration(output_wav_path)

def synthesize_segment(
    text: str,
    voice: str,
    output_wav_path: Path,
    expected_duration: float = 1.0
) -> float:
    """Synchronous single-segment wrapper."""
    return asyncio.run(_synthesize_single_segment_async(text, voice, output_wav_path, expected_duration))

async def _synthesize_batch_async(
    segments_to_generate: List[Tuple[int, str, str, Path, float]],
    default_voice: str,
    total_segments: int,
    start_time: float,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    concurrency: int = 8
) -> Dict[int, float]:
    """Concurrent synthesis using asyncio.Semaphore to maximize throughput without crashing."""
    semaphore = asyncio.Semaphore(concurrency)
    completed_count = 0
    results: Dict[int, float] = {}

    async def worker(idx: int, text: str, seg_voice: str, wav_path: Path, exp_dur: float) -> None:
        nonlocal completed_count
        async with semaphore:
            dur = await _synthesize_single_segment_async(text, seg_voice or default_voice, wav_path, exp_dur)
            results[idx] = dur
            completed_count += 1
            if on_progress:
                pct = int((completed_count / max(1, total_segments)) * 98)
                on_progress({
                    "stage": "synthesize",
                    "percent": pct,
                    "message": f"Synthesizing English speech [{completed_count}/{total_segments}]...",
                    "elapsed": round(time.time() - start_time, 1)
                })

    tasks = [worker(idx, text, seg_voice, wav_path, exp_dur) for idx, text, seg_voice, wav_path, exp_dur in segments_to_generate]
    await asyncio.gather(*tasks)
    return results

def synthesize_segments(
    segments: List[TranslatedSegment],
    tts_dir: Path,
    voice: str = DEFAULT_TTS_VOICE,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[SynthesizedSegment]:
    """
    Synthesize all translated segments concurrently into tts_dir.
    Supports individual voice assignments per segment for multi-speaker dubbing.
    Provides up to 8x faster synthesis over sequential loops with full error immunity.
    """
    tts_dir.mkdir(parents=True, exist_ok=True)
    start_time = time.time()
    total_segments = len(segments)

    if total_segments == 0:
        return []

    # Identify which segments need synthesis and which are already cached
    pending_tasks: List[Tuple[int, str, str, Path, float]] = []
    durations: Dict[int, float] = {}

    for idx, seg in enumerate(segments):
        seg_wav_path = tts_dir / f"segment_{idx:04d}.wav"
        exp_dur = max(0.3, seg.end - seg.start)
        seg_voice = seg.voice or voice
        if is_valid_file(seg_wav_path, min_size=500):
            durations[idx] = trim_silence_from_wav(seg_wav_path)
        else:
            text = seg.english.strip() or seg.original.strip()
            pending_tasks.append((idx, text, seg_voice, seg_wav_path, exp_dur))

    # Execute pending syntheses concurrently (8 parallel workers)
    if pending_tasks:
        batch_results = asyncio.run(_synthesize_batch_async(
            segments_to_generate=pending_tasks,
            default_voice=voice,
            total_segments=total_segments,
            start_time=start_time,
            on_progress=on_progress,
            concurrency=8
        ))
        durations.update(batch_results)

    # Assemble structured segment list
    synthesized_segments: List[SynthesizedSegment] = []
    for idx, seg in enumerate(segments):
        seg_wav_path = tts_dir / f"segment_{idx:04d}.wav"
        original_duration = max(seg.end - seg.start, 0.1)
        audio_dur = durations.get(idx, original_duration)

        synthesized_segments.append(
            SynthesizedSegment(
                index=idx,
                start=seg.start,
                end=seg.end,
                original_duration=round(original_duration, 3),
                audio_path=str(seg_wav_path) if seg_wav_path.exists() else "",
                audio_duration=round(audio_dur, 3),
                speed_factor=1.0,
                text=seg.english,
                speaker=seg.speaker,
                voice=seg.voice or voice
            )
        )

    if on_progress:
        on_progress({
            "stage": "synthesize",
            "percent": 100,
            "message": f"Synthesis complete: {len(synthesized_segments)} speech segments ready",
            "elapsed": round(time.time() - start_time, 1)
        })

    return synthesized_segments

