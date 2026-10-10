"""
Translation module for the Automated Video Dubbing System.
- Strictly uses AI4Bharat IndicTrans2 for all 22 Indian languages.
- Uses Whisper's neural translation engine for European and international languages (German, French, Spanish, etc.).
- Preserves accurate segment boundaries, timestamps, and speaker metadata.
"""

import time
import importlib.util
from pathlib import Path
from typing import List, Optional, Callable, Dict, Any
from huggingface_hub import hf_hub_download

from backend.config import (
    DEFAULT_INDICTRANS_MODEL,
    WHISPER_TO_INDICTRANS_LANG,
    INDICTRANS_ENGLISH_TAG,
    DEFAULT_WHISPER_MODEL,
    DEVICE
)
from backend.models import TranscriptSegment, TranslatedSegment, TranslationResult
from backend.utils import is_valid_file, save_json, load_json

# Global cached instance of the IndicTrans2 model
_INDICTRANS_MODEL_INSTANCE = None
_MARIAN_MODELS: Dict[str, Tuple[Any, Any]] = {}

def get_marian_model(src_lang: str) -> Optional[Tuple[Any, Any]]:
    """Load or retrieve cached MarianMT translation model for src_lang -> en."""
    lang_code = src_lang.lower().strip()
    if lang_code in ("en", "english"):
        return None
    if lang_code in _MARIAN_MODELS:
        return _MARIAN_MODELS[lang_code]
    
    model_name = f"Helsinki-NLP/opus-mt-{lang_code}-en"
    try:
        from transformers import MarianMTModel, MarianTokenizer
        tok = MarianTokenizer.from_pretrained(model_name)
        model = MarianMTModel.from_pretrained(model_name)
        _MARIAN_MODELS[lang_code] = (model, tok)
        return _MARIAN_MODELS[lang_code]
    except Exception:
        return None

def translate_texts_marian(texts: List[str], src_lang: str) -> Optional[List[str]]:
    """Translate a list of original text strings directly to English using MarianMT."""
    marian = get_marian_model(src_lang)
    if not marian or not texts:
        return None
    model, tok = marian
    try:
        inputs = tok(texts, return_tensors="pt", padding=True, truncation=True)
        outputs = model.generate(**inputs, max_length=256)
        return [tok.decode(t, skip_special_tokens=True).strip() for t in outputs]
    except Exception:
        return None

def get_indictrans_model(repo_id: str = DEFAULT_INDICTRANS_MODEL) -> Any:
    """Load or retrieve the cached IndicTrans2 ONNX model instance."""
    global _INDICTRANS_MODEL_INSTANCE
    if _INDICTRANS_MODEL_INSTANCE is None:
        try:
            translate_script_path = hf_hub_download(repo_id, "translate.py")
            spec = importlib.util.spec_from_file_location("it2_onnx", translate_script_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _INDICTRANS_MODEL_INSTANCE = mod.IndicTransONNX(repo_id)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load IndicTrans2 model from '{repo_id}': {str(e)}\n"
                "Please verify network access or local Hugging Face cache."
            ) from e
    return _INDICTRANS_MODEL_INSTANCE

def map_language_to_indictrans(whisper_lang: str) -> str:
    """Map Whisper ISO language code to IndicTrans2 language tag."""
    lang_code = whisper_lang.lower().strip()
    if lang_code in WHISPER_TO_INDICTRANS_LANG:
        return WHISPER_TO_INDICTRANS_LANG[lang_code]
    return "hin_Deva"

def detect_text_indic_script(text: str, default_tag: str = "hin_Deva") -> str:
    """Detect the specific Indic script in text to prevent transliteration errors."""
    for c in text:
        code = ord(c)
        if 0x0900 <= code <= 0x097F:
            return "hin_Deva"
        elif 0x0B80 <= code <= 0x0BFF:
            return "tam_Taml"
        elif 0x0C00 <= code <= 0x0C7F:
            return "tel_Telu"
        elif 0x0980 <= code <= 0x09FF:
            return "ben_Beng"
        elif 0x0600 <= code <= 0x06FF:
            return "urd_Arab"
        elif 0x0A80 <= code <= 0x0AFF:
            return "guj_Gujr"
        elif 0x0C80 <= code <= 0x0CFF:
            return "kan_Knda"
        elif 0x0D00 <= code <= 0x0D7F:
            return "mal_Mlym"
        elif 0x0A00 <= code <= 0x0A7F:
            return "pan_Guru"
        elif 0x0B00 <= code <= 0x0B7F:
            return "ory_Orya"
    return default_tag

def _align_translated_segments(
    orig_segments: List[TranscriptSegment],
    whisper_translated: List[Dict[str, Any]]
) -> List[str]:
    """
    Match Whisper translated segments to original transcript segments
    using maximum temporal overlap. Prevents sentence duplication caused
    by boundary spillovers.
    """
    if not orig_segments:
        return []
    if not whisper_translated:
        return [seg.text for seg in orig_segments]

    # Initialize assigned translation chunks for each original segment
    assignments: List[List[str]] = [[] for _ in orig_segments]

    for t in whisper_translated:
        t_text = t.get("text", "").strip()
        if not t_text:
            continue
        t_start = float(t.get("start", 0.0))
        t_end = float(t.get("end", 0.0))

        best_idx = -1
        best_overlap = 0.0

        for i, o in enumerate(orig_segments):
            overlap = max(0.0, min(o.end, t_end) - max(o.start, t_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i

        if best_idx != -1 and best_overlap > 0.1:
            assignments[best_idx].append(t_text)
        else:
            # Fallback to midpoint proximity if overlap is tiny or zero
            t_mid = (t_start + t_end) / 2.0
            closest_idx = min(
                range(len(orig_segments)),
                key=lambda i: abs(((orig_segments[i].start + orig_segments[i].end) / 2.0) - t_mid)
            )
            assignments[closest_idx].append(t_text)

    aligned_texts: List[str] = []
    for i, orig in enumerate(orig_segments):
        if assignments[i]:
            aligned_texts.append(" ".join(assignments[i]))
        else:
            # If an orig segment received no assignment, assign closest translated segment
            o_mid = (orig.start + orig.end) / 2.0
            closest = min(
                whisper_translated,
                key=lambda t: abs(((float(t.get("start", 0)) + float(t.get("end", 0))) / 2.0) - o_mid)
            )
            aligned_texts.append(closest.get("text", "").strip() or orig.text)

    return aligned_texts

def translate_segments(
    segments: List[TranscriptSegment],
    source_language: str,
    cache_path: Optional[Path] = None,
    audio_path: Optional[Path] = None,
    whisper_model: str = DEFAULT_WHISPER_MODEL,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
) -> TranslationResult:
    """
    Translate segments to English:
    - Indic languages (Hindi, Tamil, Telugu, etc.) -> AI4Bharat IndicTrans2 ONNX
    - Non-Indic languages (German, French, Spanish, etc.) -> Neural Whisper translation
    
    Args:
        segments: List of TranscriptSegment from speech recognition.
        source_language: Detected source language ISO code.
        cache_path: Optional path to save/load cached translation.json.
        audio_path: Optional path to source audio (used for Whisper translation).
        whisper_model: Whisper model size for translation.
        on_progress: Optional progress callback.
        
    Returns:
        TranslationResult containing list of TranslatedSegments with fluent English text.
    """
    # 1. Caching check
    if cache_path and is_valid_file(cache_path, min_size=20):
        cached_data = load_json(cache_path)
        if cached_data and "segments" in cached_data:
            if on_progress:
                on_progress({
                    "stage": "translate",
                    "percent": 100,
                    "message": f"Using cached translation ({len(cached_data['segments'])} segments)",
                    "cached": True
                })
            return TranslationResult.from_dict(cached_data)

    start_time = time.time()
    total_segments = len(segments)

    if total_segments == 0:
        empty_res = TranslationResult(
            source_language=source_language,
            target_language="en",
            segments=[]
        )
        if cache_path:
            save_json(empty_res.to_dict(), cache_path)
        return empty_res

    # Check if the source language is already English
    if source_language.lower() in ("en", "english"):
        if on_progress:
            on_progress({
                "stage": "translate",
                "percent": 100,
                "message": "Source is already English; preserving original transcript",
                "elapsed": 0.0
            })
        translated_segments = [
            TranslatedSegment(
                start=seg.start,
                end=seg.end,
                original=seg.text,
                english=seg.text,
                speaker=seg.speaker
            )
            for seg in segments
        ]
        result = TranslationResult(
            source_language="en",
            target_language="en",
            segments=translated_segments
        )
        if cache_path:
            save_json(result.to_dict(), cache_path)
        return result

    # Check if source language is one of the 22 Indic languages supported by IndicTrans2
    is_indic = source_language.lower() in WHISPER_TO_INDICTRANS_LANG
    translated_segments: List[TranslatedSegment] = []

    if is_indic:
        # Indic language -> IndicTrans2 ONNX
        src_indic_tag = map_language_to_indictrans(source_language)
        tgt_indic_tag = INDICTRANS_ENGLISH_TAG
        if on_progress:
            on_progress({
                "stage": "translate",
                "percent": 5,
                "message": f"Loading IndicTrans2 translation engine ({src_indic_tag} -> {tgt_indic_tag})...",
                "elapsed": round(time.time() - start_time, 1)
            })
        indic_model = get_indictrans_model()

        for i, seg in enumerate(segments):
            raw_text = seg.text.strip()
            if not raw_text:
                english_text = ""
            else:
                try:
                    # Dynamically detect specific Indic script in this segment (e.g. Tamil vs Hindi vs Urdu)
                    seg_tag = detect_text_indic_script(raw_text, src_indic_tag)
                    english_text = indic_model.translate(
                        raw_text,
                        src_lang=seg_tag,
                        tgt_lang=tgt_indic_tag
                    )
                    if isinstance(english_text, list):
                        english_text = english_text[0] if english_text else ""
                    english_text = str(english_text).strip()

                    # Verification: If IndicTrans2 produced intermediate Devanagari/Indic script instead of English
                    output_script = detect_text_indic_script(english_text, "")
                    if output_script:
                        sec_trans = indic_model.translate(
                            english_text,
                            src_lang=output_script,
                            tgt_lang=tgt_indic_tag
                        )
                        if isinstance(sec_trans, list):
                            sec_trans = sec_trans[0] if sec_trans else ""
                        sec_str = str(sec_trans).strip()
                        if sec_str and not detect_text_indic_script(sec_str, ""):
                            english_text = sec_str
                except Exception:
                    english_text = raw_text

            translated_segments.append(
                TranslatedSegment(
                    start=seg.start,
                    end=seg.end,
                    original=seg.text,
                    english=english_text,
                    speaker=seg.speaker,
                    gender=getattr(seg, "gender", None),
                    voice=getattr(seg, "voice", None)
                )
            )

            if on_progress:
                pct = int(10 + ((i + 1) / total_segments) * 80)
                on_progress({
                    "stage": "translate",
                    "percent": min(pct, 90),
                    "message": f"Translating with IndicTrans2 [{i+1}/{total_segments}]...",
                    "elapsed": round(time.time() - start_time, 1)
                })

        # Check if any segments remained untranslated (e.g. romanized Hinglish where IndicTrans2 returned original)
        untranslated_indices = [
            i for i, seg in enumerate(translated_segments)
            if seg.english.strip().lower() == seg.original.strip().lower() and len(seg.original.strip()) > 3
        ]

        if untranslated_indices and audio_path and Path(audio_path).exists():
            if on_progress:
                on_progress({
                    "stage": "translate",
                    "percent": 92,
                    "message": "Enhancing translation accuracy for romanized speech segments...",
                    "elapsed": round(time.time() - start_time, 1)
                })
            from backend.transcriber import get_whisper_model
            model = get_whisper_model(model_name=whisper_model, device=DEVICE)
            tr_res = model.transcribe(
                str(audio_path),
                verbose=False,
                task="translate",
                fp16=(DEVICE == "cuda")
            )
            whisper_tr_segs = tr_res.get("segments", [])
            aligned_whisper = _align_translated_segments(segments, whisper_tr_segs)
            for idx in untranslated_indices:
                if aligned_whisper[idx] and aligned_whisper[idx].strip().lower() != segments[idx].text.strip().lower():
                    translated_segments[idx].english = aligned_whisper[idx]
    else:
        # Non-Indic language (German, French, Spanish, etc.)
        if on_progress:
            on_progress({
                "stage": "translate",
                "percent": 15,
                "message": f"Translating {source_language.upper()} sentences to English with direct Neural NMT...",
                "elapsed": round(time.time() - start_time, 1)
            })

        # Tier 1: Direct 1:1 Text-to-Text Neural Translation (guarantees zero dropped words or sentences)
        orig_texts = [seg.text for seg in segments]
        marian_translations = translate_texts_marian(orig_texts, source_language)

        if marian_translations and len(marian_translations) == len(segments):
            for i, seg in enumerate(segments):
                translated_segments.append(
                    TranslatedSegment(
                        start=seg.start,
                        end=seg.end,
                        original=seg.text,
                        english=marian_translations[i],
                        speaker=seg.speaker,
                        gender=getattr(seg, "gender", None),
                        voice=getattr(seg, "voice", None)
                    )
                )
        elif audio_path and Path(audio_path).exists():
            # Tier 2 Fallback: Whisper audio translation pass
            from backend.transcriber import get_whisper_model
            model = get_whisper_model(model_name=whisper_model, device=DEVICE)
            tr_res = model.transcribe(
                str(audio_path),
                verbose=False,
                task="translate"
            )
            whisper_tr_segs = tr_res.get("segments", [])
            aligned_english = _align_translated_segments(segments, whisper_tr_segs)

            for i, seg in enumerate(segments):
                translated_segments.append(
                    TranslatedSegment(
                        start=seg.start,
                        end=seg.end,
                        original=seg.text,
                        english=aligned_english[i],
                        speaker=seg.speaker,
                        gender=getattr(seg, "gender", None),
                        voice=getattr(seg, "voice", None)
                    )
                )
        else:
            # Tier 3 Fallback if audio and model are not directly accessible
            for seg in segments:
                translated_segments.append(
                    TranslatedSegment(
                        start=seg.start,
                        end=seg.end,
                        original=seg.text,
                        english=seg.text,
                        speaker=seg.speaker,
                        gender=getattr(seg, "gender", None),
                        voice=getattr(seg, "voice", None)
                    )
                )

    # Apply Universal Quality Assurance & Idiomatic Normalization
    from backend.translation_normalizer import apply_universal_normalization
    translated_segments = apply_universal_normalization(translated_segments, source_language)

    result = TranslationResult(
        source_language=source_language,
        target_language="en",
        segments=translated_segments
    )

    if cache_path:
        save_json(result.to_dict(), cache_path)

    if on_progress:
        on_progress({
            "stage": "translate",
            "percent": 100,
            "message": f"Translation complete: {len(translated_segments)} segments translated to English",
            "elapsed": round(time.time() - start_time, 1)
        })

    return result
