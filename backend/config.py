"""
Configuration module for Automated Video Dubbing System.
Centralizes paths, model defaults, hardware detection, and language mappings.
"""

import os
import sys
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / os.getenv("DATA_DIR", "data")
JOBS_DIR = BASE_DIR / os.getenv("JOBS_DIR", "data/jobs")
CACHE_DIR = BASE_DIR / os.getenv("CACHE_DIR", "data/cache")
OUTPUTS_DIR = BASE_DIR / os.getenv("OUTPUTS_DIR", "data/outputs")

# Ensure required directories exist
for directory in (DATA_DIR, JOBS_DIR, CACHE_DIR, OUTPUTS_DIR):
    directory.mkdir(parents=True, exist_ok=True)

# Hardware Detection & Device Setup
def detect_device() -> str:
    """Detect available compute device with fallback to CPU."""
    configured_device = os.getenv("DEVICE", "").lower().strip()
    if configured_device in ("cuda", "cpu"):
        if configured_device == "cuda":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda"
            except Exception:
                pass
            return "cpu"
        return "cpu"

    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"

DEVICE = detect_device()

# Whisper settings
DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# IndicTrans2 settings
DEFAULT_INDICTRANS_MODEL = os.getenv(
    "INDICTRANS_MODEL", "hari31416/indictrans2-indic-en-dist-200M-ONNX"
)

# TTS settings
DEFAULT_TTS_VOICE = os.getenv("DEFAULT_TTS_VOICE", "en-US-ChristopherNeural")

# FFmpeg discovery and PATH injection
def resolve_ffmpeg_path() -> str:
    """Find a functional FFmpeg executable."""
    # 1. System path
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 2. Virtual environment Scripts directory
    venv_ffmpeg = Path(sys.executable).parent / "ffmpeg.exe"
    if venv_ffmpeg.exists():
        ffmpeg_dir = str(venv_ffmpeg.parent)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        return str(venv_ffmpeg)

    # 3. imageio_ffmpeg binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            # Ensure folder is in PATH
            exe_dir = os.path.dirname(exe)
            if exe_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = exe_dir + os.pathsep + os.environ.get("PATH", "")
            return exe
    except Exception:
        pass

    return "ffmpeg"

FFMPEG_PATH = resolve_ffmpeg_path()

# Mapping from Whisper 2-letter ISO language codes to IndicTrans2 language tags
# IndicTrans2 covers all 22 scheduled Indian languages
WHISPER_TO_INDICTRANS_LANG = {
    "hi": "hin_Deva",  # Hindi
    "bn": "ben_Beng",  # Bengali
    "ta": "tam_Taml",  # Tamil
    "te": "tel_Telu",  # Telugu
    "mr": "mar_Deva",  # Marathi
    "gu": "guj_Gujr",  # Gujarati
    "kn": "kan_Knda",  # Kannada
    "ml": "mal_Mlym",  # Malayalam
    "pa": "pan_Guru",  # Punjabi
    "ur": "urd_Arab",  # Urdu
    "or": "ory_Orya",  # Odia
    "as": "asm_Beng",  # Assamese
    "ne": "npi_Deva",  # Nepali
    "sa": "san_Deva",  # Sanskrit
    "sd": "snd_Deva",  # Sindhi
    "ks": "kas_Arab",  # Kashmiri
    "mai": "mai_Deva", # Maithili
    "brx": "brx_Deva", # Bodo
    "doi": "doi_Deva", # Dogri
    "kok": "gom_Deva", # Konkani
    "gom": "gom_Deva", # Konkani
    "mni": "mni_Mtei", # Manipuri
    "sat": "sat_Olck", # Santali
}

# Target language for IndicTrans2 (English in Latin script)
INDICTRANS_ENGLISH_TAG = "eng_Latn"
