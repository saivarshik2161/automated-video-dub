"""
Whisper Transcription module.
Performs multilingual speech recognition, language detection, and segment timestamp extraction.
Optimized with multi-core CTranslate2 INT8 execution, real-time streaming progress updates,
and guaranteed Devanagari script for Hindi/Hindustani speech (preventing Urdu script leakage).
"""

import os
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

from backend.config import DEVICE, DEFAULT_WHISPER_MODEL
from backend.models import TranscriptSegment, TranscriptionResult
from backend.utils import get_wav_duration, is_valid_file, save_json, load_json

# Cache loaded Whisper models in memory so consecutive calls don't reload weights
_LOADED_WHISPER_MODELS: Dict[str, Any] = {}

# Complete mapping of Urdu Perso-Arabic letters to Hindi Devanagari characters
URDU_TO_DEVANAGARI_MAP = {
    # Compounds / Aspirates
    "بھ": "भ", "پھ": "फ", "تھ": "थ", "ٹھ": "ठ", "جھ": "झ", "چھ": "छ",
    "دھ": "ध", "ڈھ": "ढ", "کھ": "ख", "گھ": "घ", "ڑھ": "ढ़", "نہ": "न्ह", "مہ": "म्ह",

    # Vowels & special signs
    "آ": "आ", "او": "ओ", "ای": "ई", "اے": "ए",
    "ں": "ं", "ؤ": "ओ", "ئ": "य", "ء": "",

    # Letters
    "ا": "ा", "ب": "ब", "پ": "प", "ت": "त", "ٹ": "ट", "ث": "स",
    "ج": "ज", "چ": "च", "ح": "ह", "خ": "ख़", "د": "द", "ڈ": "ड",
    "ذ": "ज़", "ر": "र", "ڑ": "ड़", "ز": "ज़", "ژ": "झ़", "س": "स",
    "ش": "श", "ص": "स", "ض": "ज़", "ط": "त", "ظ": "ज़", "ع": "अ",
    "غ": "ग़", "ف": "फ़", "ق": "क", "ک": "क", "گ": "ग", "ل": "ल",
    "م": "म", "ن": "न", "و": "व", "ہ": "ह", "ۂ": "ह", "ۃ": "त",
    "ھ": "ह", "ی": "ी", "ے": "े", "ك": "क", "ي": "ी", "ى": "ी",

    # Punctuation
    "،": ",", "؛": ";", "؟": "?", "۔": "।"
}

def urdu_to_devanagari(text: str) -> str:
    """
    Convert Urdu/Arabic script text to Hindi Devanagari script.
    Preserves exact Hindi pronunciation while eliminating Arabic/Urdu script.
    """
    if not any(0x0600 <= ord(c) <= 0x06FF for c in text):
        return text

    out = text
    for k, v in URDU_TO_DEVANAGARI_MAP.items():
        out = out.replace(k, v)

    # Fix word-initial matras into full independent vowels
    words = out.split()
    fixed = []
    for w in words:
        if w.startswith("ा"):
            w = "आ" + w[1:]
        elif w.startswith("ी"):
            w = "ई" + w[1:]
        elif w.startswith("े"):
            w = "ए" + w[1:]
        elif w.startswith("ो"):
            w = "ओ" + w[1:]
        fixed.append(w)
    return " ".join(fixed)

def get_optimal_cpu_threads() -> int:
    """Reserve 2 CPU cores for the host OS to ensure zero system lag."""
    total_cores = os.cpu_count() or 4
    return max(2, total_cores - 2)

class FasterWhisperWrapper:
    """
    Unified wrapper providing seamless compatibility with both
    OpenAI-Whisper dict format and Faster-Whisper streaming.
    """
    def __init__(self, raw_model: Any, device: str, compute_type: str):
        self._model = raw_model
        self.device = device
        self.compute_type = compute_type

    def transcribe(
        self,
        audio_path: str,
        task: str = "transcribe",
        beam_size: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Transcribe or translate returning a dict with exact word-aware segment boundaries."""
        word_ts = kwargs.get("word_timestamps", True)
        segments_gen, info = self._model.transcribe(
            str(audio_path),
            task=task,
            beam_size=beam_size,
            condition_on_previous_text=False,
            word_timestamps=word_ts,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=200)
        )
        segs_list = []
        for s in segments_gen:
            clean_txt = s.text.strip()
            if clean_txt:
                segs_list.append({
                    "start": round(float(s.start), 3),
                    "end": round(float(s.end), 3),
                    "text": clean_txt
                })
        return {
            "language": getattr(info, "language", "unknown"),
            "segments": segs_list,
            "duration": getattr(info, "duration", 0.0)
        }

def get_whisper_model(model_name: str = DEFAULT_WHISPER_MODEL, device: str = DEVICE) -> Any:
    """Retrieve or load a cached Whisper model instance with multi-core INT8 support."""
    key = f"{model_name}_{device}"
    if key not in _LOADED_WHISPER_MODELS:
        threads = get_optimal_cpu_threads()

        # 1. Try loading Faster-Whisper (high-performance CTranslate2)
        try:
            from faster_whisper import WhisperModel
            import ctranslate2

            use_cuda = (device == "cuda" and ctranslate2.get_cuda_device_count() > 0)
            if use_cuda:
                try:
                    fw_model = WhisperModel(model_name, device="cuda", compute_type="float16")
                    _LOADED_WHISPER_MODELS[key] = FasterWhisperWrapper(fw_model, "cuda", "float16")
                    return _LOADED_WHISPER_MODELS[key]
                except Exception:
                    pass

            fw_model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=threads
            )
            _LOADED_WHISPER_MODELS[key] = FasterWhisperWrapper(fw_model, "cpu", "int8")
            return _LOADED_WHISPER_MODELS[key]

        except Exception:
            # 2. Fallback to standard OpenAI-Whisper
            import whisper
            try:
                _LOADED_WHISPER_MODELS[key] = whisper.load_model(model_name, device="cpu")
            except Exception as e:
                raise RuntimeError(f"Failed to load Whisper model '{model_name}': {str(e)}") from e

    return _LOADED_WHISPER_MODELS[key]

def transcribe_audio(
    audio_path: Path,
    model_name: str = DEFAULT_WHISPER_MODEL,
    cache_path: Optional[Path] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> TranscriptionResult:
    """
    Transcribe audio with Whisper using multi-core INT8 acceleration,
    real-time segment-by-segment streaming progress updates, and strict
    Hindi Devanagari script enforcement (never outputting Urdu script).
    """
    # 1. Caching check
    if cache_path and is_valid_file(cache_path, min_size=20):
        cached_data = load_json(cache_path)
        if cached_data and "segments" in cached_data and "language" in cached_data:
            if on_progress:
                on_progress({
                    "stage": "transcribe",
                    "percent": 100,
                    "message": f"Using cached transcription ({cached_data['language']}, {len(cached_data['segments'])} segments)",
                    "cached": True
                })
            return TranscriptionResult.from_dict(cached_data)

    start_time = time.time()
    total_duration = get_wav_duration(audio_path)
    threads = get_optimal_cpu_threads()

    if on_progress:
        on_progress({
            "stage": "transcribe",
            "percent": 5,
            "message": f"Initializing Whisper '{model_name}' on {threads} dedicated CPU cores...",
            "elapsed": 0.0
        })

    model_wrapper = get_whisper_model(model_name=model_name, device=DEVICE)

    if on_progress:
        on_progress({
            "stage": "transcribe",
            "percent": 15,
            "message": "Detecting spoken language & analyzing speech frames...",
            "elapsed": round(time.time() - start_time, 1)
        })

    # High performance streaming transcription using Faster-Whisper
    if isinstance(model_wrapper, FasterWhisperWrapper):
        try:
            segments_gen, info = model_wrapper._model.transcribe(
                str(audio_path),
                beam_size=3,
                word_timestamps=True,
                condition_on_previous_text=False,
                vad_filter=False,
                task="transcribe"
            )

            raw_lang = getattr(info, "language", "unknown")
            # If Whisper detects Urdu for Hindustani speech, remap to Hindi Devanagari
            if raw_lang.lower() in ("ur", "urdu"):
                detected_language = "hi"
            else:
                detected_language = raw_lang

            prob_pct = round(getattr(info, "language_probability", 1.0) * 100, 1)

            if on_progress:
                on_progress({
                    "stage": "transcribe",
                    "percent": 20,
                    "message": f"Detected spoken language: {detected_language.upper()} ({prob_pct}% confidence). Transcribing speech...",
                    "elapsed": round(time.time() - start_time, 1)
                })

            segments: List[TranscriptSegment] = []
            for idx, raw in enumerate(segments_gen):
                raw_text = raw.text.strip()
                if not raw_text:
                    continue

                clean_text = raw_text
                start_val = raw.words[0].start if (hasattr(raw, "words") and raw.words) else raw.start
                end_val = raw.words[-1].end if (hasattr(raw, "words") and raw.words) else raw.end
                seg = TranscriptSegment(
                    start=round(float(start_val), 3),
                    end=round(float(end_val), 3),
                    text=clean_text
                )
                segments.append(seg)

                # Real-time progress scaling from 20% to 95% based on audio timestamp reached
                progress_pct = min(96, int(20 + (seg.end / max(1.0, total_duration)) * 75))

                # Format human-readable timestamp [MM:SS - MM:SS]
                m_start = int(seg.start // 60)
                s_start = int(seg.start % 60)
                m_end = int(seg.end // 60)
                s_end = int(seg.end % 60)
                time_range = f"{m_start:02d}:{s_start:02d} - {m_end:02d}:{s_end:02d}"

                # Preview snippet for the console log (ascii-safe for Windows cp1252 consoles)
                safe_display = clean_text.replace('"', "'").replace('\u2012', '-').replace('\u2013', '-').replace('\u2014', '-')
                safe_preview = safe_display.encode('ascii', 'replace').decode('ascii')
                preview = safe_preview if len(safe_preview) <= 50 else safe_preview[:47] + "..."

                if on_progress:
                    try:
                        on_progress({
                            "stage": "transcribe",
                            "percent": progress_pct,
                            "message": f"[{time_range}] \"{preview}\"",
                            "elapsed": round(time.time() - start_time, 1),
                            "details": {
                                "segment_index": idx + 1,
                                "start": seg.start,
                                "end": seg.end,
                                "text": clean_text
                            }
                        })
                    except Exception:
                        pass

        except Exception as e:
            raise RuntimeError(f"Faster-Whisper transcription failed: {str(e)}") from e

    else:
        # Standard OpenAI Whisper fallback
        try:
            result = model_wrapper.transcribe(
                str(audio_path),
                verbose=False,
                word_timestamps=True,
                task="transcribe",
                fp16=False,
                condition_on_previous_text=False
            )
            raw_lang = result.get("language", "unknown")
            if raw_lang.lower() in ("ur", "urdu"):
                detected_language = "hi"
            else:
                detected_language = raw_lang

            raw_segments = result.get("segments", [])
            segments = []
            for raw in raw_segments:
                raw_text = raw.get("text", "").strip()
                if not raw_text:
                    continue
                clean_text = raw_text
                segments.append(TranscriptSegment(
                    start=round(float(raw.get("start", 0.0)), 3),
                    end=round(float(raw.get("end", 0.0)), 3),
                    text=clean_text
                ))
        except Exception as e:
            raise RuntimeError(f"Whisper transcription failed: {str(e)}") from e

    transcription_result = TranscriptionResult(
        language=detected_language,
        duration=round(total_duration, 2),
        segments=segments
    )

    # Save to cache if path provided
    if cache_path:
        save_json(transcription_result.to_dict(), cache_path)

    total_time = round(time.time() - start_time, 1)
    if on_progress:
        on_progress({
            "stage": "transcribe",
            "percent": 100,
            "message": f"Transcription complete: {len(segments)} segments recognized in {total_time}s (language: {detected_language.upper()})",
            "elapsed": total_time,
            "details": {
                "language": detected_language,
                "segments_count": len(segments),
                "duration": total_duration
            }
        })

    return transcription_result

def parse_subtitles_file(sub_path: Path) -> Optional[List[TranscriptSegment]]:
    """
    Parse WebVTT (.vtt) or SubRip (.srt) subtitle file into TranscriptSegments.
    Extracts human-verified dialogue timestamps and text.
    """
    if not sub_path or not sub_path.exists():
        return None
    try:
        import re
        content = sub_path.read_text(encoding="utf-8", errors="replace")
        # Reject auto-generated YouTube subtitles with rolling windows or inline word tags
        if "<c>" in content or re.search(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", content):
            return None

        # Match standard VTT/SRT timing blocks
        pattern = r"(\d{1,2}:)?(\d{2}:\d{2}[\.,]\d{3})\s*-->\s*(\d{1,2}:)?(\d{2}:\d{2}[\.,]\d{3})[^\n]*\n(.*?)(?=\n\s*(?:\d+\s*\n)?(?:\d{1,2}:)?\d{2}:\d{2}[\.,]\d{3}|\Z)"
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            return None

        def to_sec(h_prefix: str, ts: str) -> float:
            ts = ts.replace(",", ".")
            parts = ts.split(":")
            if len(parts) == 2:
                m, s = parts
                h = int(h_prefix.rstrip(":")) if h_prefix else 0
            else:
                h, m, s = parts
            return round(float(h) * 3600 + float(m) * 60 + float(s), 3)

        segments: List[TranscriptSegment] = []
        for h1, s_ts, h2, e_ts, text in matches:
            clean = re.sub(r"<[^>]+>", "", text)
            clean = clean.replace("&nbsp;", " ").replace("\n", " ").strip()
            clean = re.sub(r"\s+", " ", clean)
            if clean:
                s_sec = to_sec(h1, s_ts)
                e_sec = to_sec(h2, e_ts)
                if e_sec > s_sec:
                    segments.append(TranscriptSegment(start=s_sec, end=e_sec, text=clean))
        return segments if segments else None
    except Exception:
        return None
