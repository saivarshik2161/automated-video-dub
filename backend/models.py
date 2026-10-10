"""
Data models and typed structures for the dubbing pipeline.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict

@dataclass
class SpeakerProfile:
    speaker_id: str
    gender: str = "Male"
    voice_id: str = "en-US-ChristopherNeural"
    segment_count: int = 0
    locked: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpeakerProfile":
        return cls(
            speaker_id=str(data["speaker_id"]),
            gender=str(data.get("gender", "Male")),
            voice_id=str(data.get("voice_id", "en-US-ChristopherNeural")),
            segment_count=int(data.get("segment_count", 0)),
            locked=bool(data.get("locked", True))
        )

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    gender: Optional[str] = None
    voice: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptSegment":
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            text=str(data["text"]).strip(),
            speaker=data.get("speaker"),
            gender=data.get("gender"),
            voice=data.get("voice")
        )

@dataclass
class TranscriptionResult:
    language: str
    segments: List[TranscriptSegment]
    duration: float = 0.0
    speakers: Optional[List[SpeakerProfile]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "duration": self.duration,
            "segments": [s.to_dict() for s in self.segments],
            "speakers": [sp.to_dict() for sp in (self.speakers or [])]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptionResult":
        return cls(
            language=data["language"],
            duration=float(data.get("duration", 0.0)),
            segments=[TranscriptSegment.from_dict(s) for s in data.get("segments", [])],
            speakers=[SpeakerProfile.from_dict(sp) for sp in data.get("speakers", [])] if "speakers" in data else None
        )

@dataclass
class TranslatedSegment:
    start: float
    end: float
    original: str
    english: str
    speaker: Optional[str] = None
    gender: Optional[str] = None
    voice: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslatedSegment":
        return cls(
            start=float(data["start"]),
            end=float(data["end"]),
            original=str(data["original"]).strip(),
            english=str(data["english"]).strip(),
            speaker=data.get("speaker"),
            gender=data.get("gender"),
            voice=data.get("voice")
        )

@dataclass
class TranslationResult:
    source_language: str
    target_language: str
    segments: List[TranslatedSegment]
    speakers: Optional[List[SpeakerProfile]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_language": self.source_language,
            "target_language": self.target_language,
            "segments": [s.to_dict() for s in self.segments],
            "speakers": [sp.to_dict() for sp in (self.speakers or [])]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationResult":
        return cls(
            source_language=data["source_language"],
            target_language=data.get("target_language", "en"),
            segments=[TranslatedSegment.from_dict(s) for s in data.get("segments", [])],
            speakers=[SpeakerProfile.from_dict(sp) for sp in data.get("speakers", [])] if "speakers" in data else None
        )

@dataclass
class SynthesizedSegment:
    index: int
    start: float
    end: float
    original_duration: float
    audio_path: str
    audio_duration: float
    speed_factor: float = 1.0
    text: str = ""
    speaker: Optional[str] = None
    voice: Optional[str] = None

@dataclass
class PipelineOptions:
    multi_speaker: bool = True
    keep_background_music: bool = True
    voice_cloning: bool = False
    whisper_model: str = "small"
    tts_voice: str = "en-US-ChristopherNeural"
    speed_adjustment: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "PipelineOptions":
        if not data:
            return cls()
        return cls(
            multi_speaker=bool(data.get("multi_speaker", True)),
            keep_background_music=bool(data.get("keep_background_music", True)),
            voice_cloning=bool(data.get("voice_cloning", False)),
            whisper_model=str(data.get("whisper_model") or "small"),
            tts_voice=str(data.get("tts_voice", "en-US-ChristopherNeural")),
            speed_adjustment=bool(data.get("speed_adjustment", True))
        )

@dataclass
class ProgressEvent:
    stage: str
    percent: int
    message: str
    elapsed: float = 0.0
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
