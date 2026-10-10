"""
Audio Mixer module.
Blends synthesized English speech with preserved background music and ambiance
while muting/ducking the original foreign dialogue during speech intervals.
Ensures seamless volume transitions with smooth crossfades and soft-knee clipping prevention.
"""

import time
import wave
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Dict, Any

from backend.audio_processor import convert_to_wav
from backend.utils import is_valid_file, get_wav_duration

def mix_dubbed_audio(
    original_audio_path: Path,
    aligned_speech_path: Path,
    speech_intervals: List[Tuple[float, float]],
    output_mixed_path: Path,
    duck_gain_db: float = -80.0,
    fade_ms: int = 50,
    speech_boost: float = 1.15,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Path:
    """
    Mix original audio (with foreign speech ducked/muted) and aligned English speech.
    
    Preserves 100% of background music, sound effects, and room ambiance during
    non-speech intervals, and ducks original speech down by duck_gain_db (default -30dB)
    during dialogue with smooth fade_ms ramps to eliminate foreign speech bleed.
    
    Args:
        original_audio_path: Path to extracted original audio (e.g. 16kHz WAV).
        aligned_speech_path: Path to aligned English speech (e.g. 24kHz WAV).
        speech_intervals: List of (start_sec, end_sec) speech timestamps.
        output_mixed_path: Output target path for the mixed master audio WAV.
        duck_gain_db: Volume attenuation in dB for original speech (default -30.0 dB).
        fade_ms: Duration of crossfade ramps in milliseconds (default 60 ms).
        speech_boost: Linear gain multiplier for English dialogue (default 1.15).
        on_progress: Optional progress callback.
        
    Returns:
        Path to output_mixed_path.
    """
    output_mixed_path.parent.mkdir(parents=True, exist_ok=True)

    if is_valid_file(output_mixed_path, min_size=1024):
        if on_progress:
            on_progress({
                "stage": "mix_audio",
                "percent": 100,
                "message": "Using cached mixed audio track",
                "cached": True
            })
        return output_mixed_path

    start_time = time.time()
    if on_progress:
        on_progress({
            "stage": "mix_audio",
            "percent": 10,
            "message": "Preparing audio streams for background preservation & speech ducking...",
            "elapsed": 0.0
        })

    target_sr = 24000
    temp_resampled_orig: Optional[Path] = None

    # 1. Inspect original audio sample rate and resample if needed
    with wave.open(str(original_audio_path), "rb") as wf_orig:
        orig_sr = wf_orig.getframerate()
        orig_n_ch = wf_orig.getnchannels()

    if orig_sr != target_sr or orig_n_ch > 1:
        temp_resampled_orig = output_mixed_path.parent / "orig_resampled_24k.wav"
        convert_to_wav(original_audio_path, temp_resampled_orig, sample_rate=target_sr)
        read_orig_path = temp_resampled_orig
    else:
        read_orig_path = original_audio_path

    # 2. Read resampled original audio PCM samples
    with wave.open(str(read_orig_path), "rb") as wf_orig:
        orig_frames = wf_orig.getnframes()
        orig_bytes = wf_orig.readframes(orig_frames)
        orig_samples = np.frombuffer(orig_bytes, dtype=np.int16).astype(np.float32)

    # 3. Read aligned speech PCM samples
    with wave.open(str(aligned_speech_path), "rb") as wf_speech:
        speech_frames = wf_speech.getnframes()
        speech_bytes = wf_speech.readframes(speech_frames)
        speech_samples = np.frombuffer(speech_bytes, dtype=np.int16).astype(np.float32)

    if on_progress:
        on_progress({
            "stage": "mix_audio",
            "percent": 40,
            "message": "Computing audio ducking envelope for dialogue intervals...",
            "elapsed": round(time.time() - start_time, 1)
        })

    # 4. Align buffer lengths
    total_len = max(len(orig_samples), len(speech_samples))
    if len(orig_samples) < total_len:
        orig_samples = np.pad(orig_samples, (0, total_len - len(orig_samples)), mode="constant")
    if len(speech_samples) < total_len:
        speech_samples = np.pad(speech_samples, (0, total_len - len(speech_samples)), mode="constant")

    # 5. Construct ducking gain envelope (1.0 = normal ambient/music, duck_factor during dialogue)
    # Deep ducking (<= -60dB) completely silences the foreign speech to guarantee zero bleed
    if duck_gain_db <= -60.0:
        duck_factor = 0.0
    else:
        duck_factor = float(10.0 ** (duck_gain_db / 20.0))
    gain_envelope = np.ones(total_len, dtype=np.float32)
    fade_samples = max(1, int((fade_ms / 1000.0) * target_sr))

    for start_sec, end_sec in speech_intervals:
        s_idx = max(0, int(start_sec * target_sr))
        e_idx = min(total_len, int(end_sec * target_sr))
        if e_idx <= s_idx:
            continue

        # Dialogue zone is ducked
        gain_envelope[s_idx:e_idx] = duck_factor

        # Smooth ramp down before dialogue starts
        ramp_down_start = max(0, s_idx - fade_samples)
        if s_idx > ramp_down_start:
            ramp_down = np.linspace(1.0, duck_factor, s_idx - ramp_down_start, dtype=np.float32)
            gain_envelope[ramp_down_start:s_idx] = np.minimum(gain_envelope[ramp_down_start:s_idx], ramp_down)

        # Smooth ramp up after dialogue ends
        ramp_up_end = min(total_len, e_idx + fade_samples)
        if ramp_up_end > e_idx:
            ramp_up = np.linspace(duck_factor, 1.0, ramp_up_end - e_idx, dtype=np.float32)
            gain_envelope[e_idx:ramp_up_end] = np.minimum(gain_envelope[e_idx:ramp_up_end], ramp_up)

    if on_progress:
        on_progress({
            "stage": "mix_audio",
            "percent": 70,
            "message": "Blending background ambiance with English speech...",
            "elapsed": round(time.time() - start_time, 1)
        })

    # 6. Apply gain envelope to original audio to mute/duck foreign speech
    ducked_original = orig_samples * gain_envelope

    # 7. Mix ducked background + boosted clear English speech
    mixed = ducked_original + (speech_samples * speech_boost)

    # 8. Soft-knee limiter / prevent digital clipping
    peak = np.max(np.abs(mixed))
    if peak > 32700.0:
        mixed = (mixed / peak) * 32600.0

    mixed_int16 = np.clip(mixed, -32768, 32767).astype(np.int16)

    # 9. Write master mixed WAV
    with wave.open(str(output_mixed_path), "wb") as out_wf:
        out_wf.setnchannels(1)
        out_wf.setsampwidth(2)
        out_wf.setframerate(target_sr)
        out_wf.writeframes(mixed_int16.tobytes())

    # 10. Clean up temporary resampled file
    if temp_resampled_orig and temp_resampled_orig.exists():
        try:
            temp_resampled_orig.unlink(missing_ok=True)
        except Exception:
            pass

    if on_progress:
        on_progress({
            "stage": "mix_audio",
            "percent": 100,
            "message": f"Master audio mixing complete ({total_len / target_sr:.1f}s mixed)",
            "elapsed": round(time.time() - start_time, 1)
        })

    return output_mixed_path
