"""
Unified Pipeline module.
Central orchestration engine for the Automated Video Dubbing System.
Coordinates downloading, transcription, IndicTrans2 translation, Edge-TTS synthesis,
audio alignment, and video remuxing with multi-stage caching and structured progress reporting.
"""

import time
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from backend.config import (
    JOBS_DIR,
    OUTPUTS_DIR,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_TTS_VOICE,
    resolve_ffmpeg_path
)
from backend.models import PipelineOptions, SpeakerProfile, TranscriptionResult
from backend.utils import (
    generate_job_id,
    save_json,
    load_json,
    is_valid_file,
    get_wav_duration,
    format_duration
)
from backend.downloader import download_video
from backend.audio_processor import extract_audio
from backend.transcriber import transcribe_audio
from backend.diarizer import diarize_and_assign_voices
from backend.translator import translate_segments
from backend.synthesizer import synthesize_segments
from backend.aligner import align_audio
from backend.audio_mixer import mix_dubbed_audio
from backend.validator import validate_dubbing_pre_export
from backend.video_processor import merge_video_and_audio

def run_pipeline(
    url: str,
    options: Optional[PipelineOptions] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    force_restart: bool = False
) -> Dict[str, Any]:
    """
    Execute the end-to-end automated video dubbing pipeline.
    
    Args:
        url: Target YouTube video URL.
        options: Configuration options (voice, model, speed adjustment, etc.).
        on_progress: Optional callback invoked with progress event dictionaries.
        force_restart: If True, ignores previous caches and reruns all stages.
        
    Returns:
        Dictionary containing job metadata, paths to all intermediate and final artifacts,
        transcriptions, translations, and timing metrics.
    """
    if options is None:
        options = PipelineOptions()

    # Ensure FFmpeg is available and in PATH
    resolve_ffmpeg_path()

    pipeline_start = time.time()
    job_id = generate_job_id(url)
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Artifact paths
    source_video_path = job_dir / "source.mp4"
    audio_path = job_dir / "audio.wav"
    transcription_path = job_dir / "transcription.json"
    translation_path = job_dir / "translation.json"
    tts_dir = job_dir / "tts"
    aligned_audio_path = job_dir / "aligned_audio.wav"
    master_mixed_path = job_dir / "master_dubbed_audio.wav"
    validation_path = job_dir / "validation_report.json"
    final_dubbed_path = job_dir / "final_dubbed.mp4"
    job_meta_path = job_dir / "job_meta.json"

    if force_restart:
        for p in (final_dubbed_path, master_mixed_path, aligned_audio_path, validation_path, translation_path, transcription_path, audio_path):
            if p.exists():
                p.unlink(missing_ok=True)
        if tts_dir.exists():
            shutil.rmtree(tts_dir, ignore_errors=True)

    def report(stage: str, percent: int, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        if on_progress:
            on_progress({
                "stage": stage,
                "percent": min(max(int(percent), 0), 100),
                "message": message,
                "elapsed": round(time.time() - pipeline_start, 1),
                "job_id": job_id,
                "details": details or {}
            })

    # =========================================================================
    # STAGE 1: Download Video (yt-dlp)
    # =========================================================================
    report("download", 0, "Initializing video download...")
    downloaded_video, meta = download_video(
        url=url,
        job_dir=job_dir,
        on_progress=on_progress
    )

    # =========================================================================
    # STAGE 2: Extract Audio & Transcribe (Whisper)
    # =========================================================================
    report("transcribe", 0, "Extracting audio for Whisper transcription...")
    extracted_audio = extract_audio(
        video_path=downloaded_video,
        output_audio_path=audio_path,
        on_progress=on_progress
    )

    audio_duration = get_wav_duration(extracted_audio)

    # Check if native/official subtitles are available in job_dir
    sub_files = [f for f in job_dir.glob("*.vtt")] + [f for f in job_dir.glob("*.srt")]
    # Prioritize source language subtitles (e.g. *.de-orig.*, *.de.*, *.fr.*, etc.)
    sub_files.sort(key=lambda f: (
        0 if any(tag in f.name.lower() for tag in ["orig", ".de.", ".de-orig.", ".fr.", ".es.", ".hi.", ".it."]) else
        1 if not (".en." in f.name.lower()) else
        2
    ))
    parsed_sub_segments = None
    detected_sub_lang = "de"
    for sf in sub_files:
        from backend.transcriber import parse_subtitles_file
        parsed = parse_subtitles_file(sf)
        if parsed and len(parsed) >= 5:
            parsed_sub_segments = parsed
            import re
            m = re.search(r"\.([a-z]{2,3})\.(?:vtt|srt)$", sf.name.lower())
            if m:
                detected_sub_lang = m.group(1)
            report("transcribe", 100, f"Using verified official video subtitles ({len(parsed_sub_segments)} segments from {sf.name})")
            transcription_result = TranscriptionResult(
                language=detected_sub_lang,
                segments=parsed_sub_segments,
                duration=audio_duration
            )
            save_json(transcription_result.to_dict(), transcription_path)
            break

    if not parsed_sub_segments:
        report("transcribe", 20, f"Transcribing audio with Whisper ({options.whisper_model})...")
        transcription_result = transcribe_audio(
            audio_path=extracted_audio,
            model_name=options.whisper_model,
            cache_path=transcription_path,
            on_progress=on_progress
        )

    # =========================================================================
    # STAGE 2b: Speaker Identification & Diarization
    # =========================================================================
    report("diarize", 0, "Identifying speakers and assigning gender-matched voices...")
    if options.multi_speaker:
        diarized_segments, speaker_profiles = diarize_and_assign_voices(
            audio_path=extracted_audio,
            segments=transcription_result.segments,
            default_voice=options.tts_voice
        )
        transcription_result.segments = diarized_segments
        transcription_result.speakers = speaker_profiles
    else:
        # Single speaker mode: lock all dialogue to default_voice
        speaker_profile = SpeakerProfile(
            speaker_id="Speaker 1",
            gender="Neutral",
            voice_id=options.tts_voice,
            segment_count=len(transcription_result.segments),
            locked=True
        )
        speaker_profiles = [speaker_profile]
        for seg in transcription_result.segments:
            seg.speaker = "Speaker 1"
            seg.voice = options.tts_voice
        transcription_result.speakers = speaker_profiles

    save_json(transcription_result.to_dict(), transcription_path)
    report("diarize", 100, f"Identified {len(speaker_profiles)} distinct speaker profile(s).", details={
        "speakers": [sp.to_dict() for sp in speaker_profiles]
    })

    # =========================================================================
    # STAGE 3: Translate to English (Original Video is Sole Truth)
    # =========================================================================
    report("translate", 0, f"Translating transcript to English (from {transcription_result.language})...")
    translation_result = translate_segments(
        segments=transcription_result.segments,
        source_language=transcription_result.language,
        cache_path=translation_path,
        audio_path=extracted_audio,
        whisper_model=options.whisper_model,
        on_progress=on_progress
    )
    translation_result.speakers = speaker_profiles
    save_json(translation_result.to_dict(), translation_path)

    # =========================================================================
    # STAGE 4: Synthesize English Speech (Edge-TTS)
    # =========================================================================
    report("synthesize", 0, f"Synthesizing natural English speech ({len(speaker_profiles)} speaker voice(s))...")
    synthesized_segments = synthesize_segments(
        segments=translation_result.segments,
        tts_dir=tts_dir,
        voice=options.tts_voice,
        on_progress=on_progress
    )

    # =========================================================================
    # STAGE 5: Timing and Alignment
    # =========================================================================
    report("align", 0, "Aligning speech timestamps and scaling tempo...")
    aligned_audio = align_audio(
        synthesized_segments=synthesized_segments,
        total_duration=audio_duration,
        output_aligned_path=aligned_audio_path,
        speed_adjustment=options.speed_adjustment,
        on_progress=on_progress
    )

    # =========================================================================
    # STAGE 5b: Audio Mixing (Preserve Ambiance / Duck Foreign Dialogue)
    # =========================================================================
    master_audio_track = aligned_audio
    if options.keep_background_music:
        report("mix_audio", 0, "Ducking original foreign dialogue and blending background ambiance...")
        speech_intervals = [(s.start, s.end) for s in translation_result.segments]
        master_audio_track = mix_dubbed_audio(
            original_audio_path=extracted_audio,
            aligned_speech_path=aligned_audio,
            speech_intervals=speech_intervals,
            output_mixed_path=master_mixed_path,
            duck_gain_db=-80.0,
            fade_ms=50,
            speech_boost=1.15,
            on_progress=on_progress
        )
    else:
        report("mix_audio", 100, "Using pure synthesized dialogue track (background disabled).")

    # =========================================================================
    # STAGE 5c: Pre-Export Quality Validation Pass
    # =========================================================================
    report("validate", 0, "Performing pre-export synchronization and voice consistency validation...")
    validation_report = validate_dubbing_pre_export(
        translated_segments=translation_result.segments,
        synthesized_segments=synthesized_segments,
        speaker_profiles=speaker_profiles,
        total_audio_duration=audio_duration,
        master_audio_path=master_audio_track
    )
    save_json(validation_report, validation_path)
    report("validate", 100, f"Validation completed: {validation_report['status']} ({validation_report['passed_count']} checks passed).", details=validation_report)

    # =========================================================================
    # STAGE 6: Remux Final Video (FFmpeg)
    # =========================================================================
    report("remix", 0, "Multiplexing final master audio with original video...")
    final_video = merge_video_and_audio(
        video_path=downloaded_video,
        audio_path=master_audio_track,
        output_mp4_path=final_dubbed_path,
        on_progress=on_progress
    )

    total_processing_seconds = round(time.time() - pipeline_start, 2)

    # Save outputs copy into data/outputs for convenience
    published_output = OUTPUTS_DIR / f"{job_id}_dubbed.mp4"
    if not published_output.exists() or force_restart:
        try:
            shutil.copy2(final_video, published_output)
        except Exception:
            pass

    # Save comprehensive job metadata with speaker profiles & validation
    result_manifest = {
        "job_id": job_id,
        "url": url,
        "title": meta.get("title", "Video"),
        "duration_seconds": audio_duration,
        "duration_formatted": format_duration(audio_duration),
        "source_language": transcription_result.language,
        "whisper_model": options.whisper_model,
        "translation_model": "IndicTrans2",
        "tts_voice": options.tts_voice,
        "speakers": [sp.to_dict() for sp in (speaker_profiles or [])],
        "validation": validation_report,
        "total_processing_time": total_processing_seconds,
        "total_processing_formatted": format_duration(total_processing_seconds),
        "artifacts": {
            "source_video": str(downloaded_video),
            "audio": str(extracted_audio),
            "transcription": str(transcription_path),
            "translation": str(translation_path),
            "tts_dir": str(tts_dir),
            "aligned_audio": str(aligned_audio),
            "alignment_manifest": str(job_dir / "alignment_manifest.json"),
            "master_audio": str(master_audio_track),
            "validation_report": str(validation_path),
            "final_dubbed": str(final_video),
            "published_output": str(published_output) if published_output.exists() else str(final_video)
        },
        "transcript_count": len(transcription_result.segments),
        "status": "completed"
    }

    save_json(result_manifest, job_meta_path)

    report("remix", 100, "Dubbing completed successfully!", details=result_manifest)

    return result_manifest
