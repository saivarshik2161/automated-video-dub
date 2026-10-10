# Automated Video Dubbing System

An end-to-end autonomous video dubbing pipeline that downloads YouTube videos in foreign languages (German, French, Hindi, Tamil, Telugu, Spanish, etc.), transcribes speech, translates into natural English, synthesizes expressive neural speech, synchronizes timing with adaptive tempo stretching, and remuxes the final video container without lossy video re-encoding.

Built with a high-performance **Python / FastAPI** backend and a polished **React + TypeScript + Vite + Tailwind CSS** frontend featuring Three.js visual computing and real-time Server-Sent Events (SSE).

---

## 🎯 Architecture Overview

```
                      YouTube Video URL
                              │
                              ▼
    ┌───────────────────────────────────────────────────┐
    │  STAGE 1: Video Downloader (yt-dlp)               │
    │  - 720p HD stream selection                       │
    │  - Node.js runtime for zero-warning YouTube extraction│
    │  - Source audio + video caching                   │
    └─────────────────────────┬─────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────┐
    │  STAGE 2: Transcription (Whisper)                 │
    │  - Multilingual automatic speech recognition     │
    │  - 16 kHz mono WAV audio extraction               │
    │  - Accurate segment timestamps & language detection│
    └─────────────────────────┬─────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────┐
    │  STAGE 3: Translation Engine                      │
    │  - Indic Languages: AI4Bharat IndicTrans2 (ONNX) │
    │    (Hindi, Tamil, Telugu, Bengali, Marathi, etc.) │
    │  - International Languages: Neural Whisper        │
    │    (German, French, Spanish, Japanese, etc.)      │
    │  - Midpoint & temporal overlap alignment          │
    └─────────────────────────┬─────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────┐
    │  STAGE 4: Speech Synthesis (Edge-TTS)             │
    │  - High-fidelity Microsoft Neural English voices  │
    │  - Asynchronous parallel batch generation         │
    │  - 24 kHz studio quality PCM master audio         │
    └─────────────────────────┬─────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────┐
    │  STAGE 5: Timing Alignment & Tempo Adjustment     │
    │  - Exact duration matching per spoken segment     │
    │  - Bounded FFmpeg atempo scaling (1.0x - 1.38x)   │
    │  - Zero pitch distortion                          │
    └─────────────────────────┬─────────────────────────┘
                              │
                              ▼
    ┌───────────────────────────────────────────────────┐
    │  STAGE 6: Video Remuxing (FFmpeg)                 │
    │  - Lossless video stream copy (-c:v copy)         │
    │  - AAC audio multiplexing                         │
    │  - Web-optimized (+faststart) container output    │
    └─────────────────────────┬─────────────────────────┘
                              │
                              ▼
                   Final Dubbed English MP4
```

---

## ⚡ Key Engineering Decisions

1. **AI4Bharat IndicTrans2 ONNX**:
   - Strictly deployed as the primary translation engine for all 22 scheduled Indian languages (Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Punjabi, Urdu, Kannada, Malayalam, etc.).
   - Employs quantized ONNX Runtime execution for sub-second CPU/GPU inference without cloud API dependencies.

2. **Native Neural Translation for International Speech**:
   - European and global languages (German, French, Spanish, Russian, etc.) leverage Whisper's neural cross-lingual translation directly from acoustic speech representations.
   - Eliminates translation failures and maintains natural colloquial phrasing.

3. **Asynchronous Concurrent Speech Synthesis**:
   - Rather than sequential segment-by-segment generation (which introduces cumulative network latency), synthesis tasks execute concurrently using `asyncio.gather` bounded by an `asyncio.Semaphore`.
   - Synthesizing 70+ spoken segments takes **~15–30 seconds** rather than several minutes.

4. **Lossless Stream Copy Remuxing**:
   - FFmpeg replaces the audio track while preserving the original video stream intact (`-c:v copy -c:a aac -movflags +faststart`).
   - Remuxing a 4-minute video completes in **~1.5 seconds** with zero compression artifacts or generation loss.

5. **Multi-Stage Disk Caching**:
   - Intermediate artifacts (`source.mp4`, `audio.wav`, `transcription.json`, `translation.json`, TTS segments) are persistently cached.
   - Long-running jobs or page refreshes resume instantly without repeating expensive compute stages.

6. **In-Process Serialized GPU Job Queue**:
   - Heavy transcription and translation tasks are orchestrated through an asynchronous background queue, ensuring GPU stability and preventing out-of-memory errors on consumer laptop GPUs (e.g., RTX 3050).

---

## 🚀 Quickstart & Setup

### Prerequisites
- **Python**: 3.10 to 3.14
- **Node.js**: v18+ (used for yt-dlp JavaScript extraction & frontend)
- **FFmpeg**: Installed or auto-resolved via `.venv/Scripts/ffmpeg.exe`

### 1. Installation
Clone the repository and set up a virtual environment:

```bash
git clone <repo-url>
cd intern

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Run the CLI Pipeline (`dub.py`)
Run the pipeline directly from your terminal with rich stage indicators:

```bash
python dub.py "https://www.youtube.com/watch?v=iVo3LfZti5w"
```

Options:
- `--voice`: Choose English TTS voice (default: `en-US-ChristopherNeural`)
- `--whisper-model`: Whisper model size (`tiny`, `base`, `small`, `medium`)
- `--output`: Custom output path for final dubbed video
- `--no-cache`: Force pipeline restart ignoring disk cache

### 3. Run the Web Application (`server.py`)
Start the FastAPI server serving both API endpoints and the built React frontend:

```bash
python server.py
```
Open **`http://localhost:8000`** in your browser.

---

## 📊 Evaluation & Verification Benchmarks

| Metric | Hindi Motivational Clip | French Story Clip | German Introduction Clip |
| :--- | :--- | :--- | :--- |
| **YouTube URL** | `watch?v=iVo3LfZti5w` | `watch?v=FTSW3mJ_z5E` | `watch?v=Yaelm87PTvg` |
| **Duration** | 57 seconds | 102 seconds | 248 seconds (04:08) |
| **Source Language** | Hindi (`hi`) | French (`fr`) | German (`de`) |
| **Translation Engine** | **IndicTrans2 ONNX** | **Whisper Neural** | **Whisper Neural** |
| **Spoken Segments** | 10 segments | 17 segments | 76 segments |
| **TTS Synthesis Time** | 3.2s | 4.8s | 28.5s |
| **Remux Time** | 0.8s | 1.1s | 1.8s |
| **Output File** | `d5d3afb3f305_dubbed.mp4` | `7d3370daec94_dubbed.mp4` | `6f1ab2081f07_dubbed.mp4` |
| **Status** | **Verified** | **Verified** | **Verified** |

---

## 📁 Repository Layout

```
.
├── backend/
│   ├── aligner.py          # Timeline speech assembler & FFmpeg tempo scaler
│   ├── audio_processor.py  # 16kHz audio extraction & format converter
│   ├── config.py           # Hardware detection, language mapping & FFmpeg discovery
│   ├── downloader.py       # yt-dlp downloader with 720p HD format selector
│   ├── job_manager.py      # Serialized async GPU job queue & SSE broadcaster
│   ├── models.py           # Typed dataclasses (Segments, Events, Results)
│   ├── pipeline.py         # Unified 6-stage dubbing orchestrator
│   ├── synthesizer.py      # Edge-TTS speech synthesizer with parallel batching
│   ├── transcriber.py      # Multilingual Whisper transcription
│   ├── translator.py       # IndicTrans2 (Indic) & Whisper (International) translation
│   ├── utils.py            # JSON persistence & WAV duration utilities
│   └── video_processor.py  # Lossless FFmpeg stream copy remuxer
├── frontend/
│   ├── src/
│   │   ├── components/     # Particle background, players, transcript table, etc.
│   │   ├── types.ts        # TypeScript API and SSE event types
│   │   ├── App.tsx         # Main interactive UI layout
│   │   └── main.tsx        # React entrypoint
│   ├── dist/               # Production compiled SPA bundle (served by server.py)
│   └── package.json        # Frontend dependencies (React, Vite, Three.js, Lucide)
├── data/
│   ├── jobs/               # Working job directories & intermediate artifacts
│   ├── cache/              # Cached downloads & model artifacts
│   └── outputs/            # Published final dubbed MP4 videos
├── dub.py                  # CLI dubbing entrypoint with Rich terminal UI
├── server.py               # FastAPI web server & static SPA host
├── requirements.txt        # Python dependencies
├── .env.example            # Environment configuration template
├── .gitignore              # Git exclusions
└── README.md               # Project documentation
```

---

## 📜 License
MIT License. Built for the Automated Video Dubbing System internship evaluation.
