"""
FastAPI Server for Automated Video Dubbing System.
Provides REST endpoints, Server-Sent Events (SSE), and byte-range video streaming.
Run with:
    python server.py
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl

from backend.config import JOBS_DIR
from backend.models import PipelineOptions
from backend.job_manager import job_manager
from backend.utils import load_json, is_valid_file

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize background queue worker on server startup."""
    loop = asyncio.get_running_loop()
    job_manager.start(loop)
    yield

app = FastAPI(
    title="AutoDub AI API",
    description="Backend API for AutoDub AI - Smart Multilingual Video Dubbing.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for web UI development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Request Models
class JobOptionsSchema(BaseModel):
    multi_speaker: bool = True
    keep_background_music: bool = True
    voice_cloning: bool = False
    whisper_model: str = "small"
    tts_voice: str = "en-US-ChristopherNeural"

class CreateJobRequest(BaseModel):
    url: str
    options: Optional[JobOptionsSchema] = None

# Helper: HTTP Range Request Video Streamer
def stream_file_with_range(path: Path, request: Request) -> Response:
    """Stream media file supporting HTTP Range requests for video seeking."""
    if not is_valid_file(path, min_size=100):
        raise HTTPException(status_code=404, detail="Requested media file not found or empty.")

    file_size = path.stat().st_size

    if request.method == "HEAD":
        return Response(
            status_code=200,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Type": "video/mp4",
            }
        )

    range_header = request.headers.get("range")

    if not range_header:
        # Standard full response
        def iterfile():
            with open(path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        return StreamingResponse(
            iterfile(),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Content-Disposition": f'inline; filename="{path.name}"'
            }
        )

    # Parse Range Header: e.g. bytes=0-1048575 or bytes=1048576-
    range_match = re.match(r"bytes=(\d+)-(\d+)?", range_header.strip())
    if not range_match:
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start_byte = int(range_match.group(1))
    end_byte = int(range_match.group(2)) if range_match.group(2) else file_size - 1

    if start_byte >= file_size or end_byte >= file_size or start_byte > end_byte:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"}
        )

    chunk_size = (end_byte - start_byte) + 1

    def iter_chunk():
        with open(path, "rb") as f:
            f.seek(start_byte)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_amount = min(bytes_left, 1024 * 512)
                data = f.read(read_amount)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }

    return StreamingResponse(
        iter_chunk(),
        status_code=206,
        headers=headers
    )

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "automated-video-dubbing"}

@app.post("/api/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(payload: CreateJobRequest):
    """
    Submit a YouTube URL for dubbing into English.
    Returns: { "job_id": "..." }
    """
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL cannot be empty.")

    opts_dict = payload.options.dict() if payload.options else {}
    options = PipelineOptions.from_dict(opts_dict)

    job = await job_manager.submit_job(url=url, options=options)
    return {"job_id": job.job_id}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Retrieve job status, active stage, and overall percentage.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found.")

    return job.to_status_dict()

@app.get("/api/jobs/{job_id}/events")
async def get_job_events(job_id: str):
    """
    Server-Sent Events (SSE) endpoint broadcasting live pipeline events.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with ID '{job_id}' not found.")

    return StreamingResponse(
        job_manager.subscribe(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.api_route("/api/jobs/{job_id}/video", methods=["GET", "HEAD"])
@app.api_route("/api/jobs/{job_id}/stream", methods=["GET", "HEAD"])
async def get_dubbed_video(job_id: str, request: Request):
    """Stream the final dubbed MP4 with native HTTP Range support for seeking."""
    video_path = JOBS_DIR / job_id / "final_dubbed.mp4"
    if not is_valid_file(video_path, min_size=100):
        raise HTTPException(status_code=404, detail="Dubbed video not found or not yet completed.")
    return FileResponse(path=str(video_path), media_type="video/mp4")

@app.api_route("/api/jobs/{job_id}/original", methods=["GET", "HEAD"])
async def get_original_video(job_id: str, request: Request):
    """Stream the downloaded original source video with native HTTP Range support."""
    video_path = JOBS_DIR / job_id / "source.mp4"
    if not is_valid_file(video_path, min_size=100):
        raise HTTPException(status_code=404, detail="Source video not found.")
    return FileResponse(path=str(video_path), media_type="video/mp4")

@app.get("/api/jobs/{job_id}/download")
async def download_dubbed_video(job_id: str):
    """
    Download the final dubbed MP4 file as an attachment.
    """
    video_path = JOBS_DIR / job_id / "final_dubbed.mp4"
    if not is_valid_file(video_path, min_size=1000):
        raise HTTPException(status_code=404, detail="Dubbed video not found or not yet completed.")

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"dubbed_{job_id}.mp4"
    )

@app.get("/api/jobs/{job_id}/transcript")
async def get_transcript(job_id: str):
    """
    Return structured transcript and translation data with timestamps.
    """
    job_dir = JOBS_DIR / job_id
    transcription_file = job_dir / "transcription.json"
    translation_file = job_dir / "translation.json"

    if not translation_file.exists():
        raise HTTPException(status_code=404, detail="Transcript/translation data not available yet.")

    translation_data = load_json(translation_file) or {}
    transcription_data = load_json(transcription_file) or {}

    segments = []
    raw_segments = translation_data.get("segments", [])
    for idx, s in enumerate(raw_segments):
        segments.append({
            "index": idx + 1,
            "start": s.get("start", 0.0),
            "end": s.get("end", 0.0),
            "speaker": s.get("speaker") or "Speaker 1",
            "gender": s.get("gender") or "Male",
            "voice": s.get("voice") or "en-US-ChristopherNeural",
            "original": s.get("original", ""),
            "english": s.get("english", "")
        })

    speakers = translation_data.get("speakers") or transcription_data.get("speakers") or []

    return {
        "job_id": job_id,
        "source_language": translation_data.get("source_language", "unknown"),
        "target_language": "en",
        "total_segments": len(segments),
        "speakers": speakers,
        "segments": segments
    }

@app.get("/api/jobs/{job_id}/meta")
async def get_job_meta(job_id: str):
    """Return full job manifest, speaker mapping, and validation report."""
    job_dir = JOBS_DIR / job_id
    meta_path = job_dir / "job_meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Job metadata not found.")
    return load_json(meta_path)

@app.get("/api/jobs/{job_id}/alignment")
async def get_job_alignment(job_id: str):
    """Return per-segment alignment manifest with absolute master clock timing metrics."""
    job_dir = JOBS_DIR / job_id
    manifest_path = job_dir / "alignment_manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Alignment manifest not found.")
    return load_json(manifest_path)

# Mount static web frontend if built
dist_dir = Path(__file__).resolve().parent / "frontend" / "dist"
if dist_dir.exists():
    from fastapi.staticfiles import StaticFiles
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = dist_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Automated Video Dubbing Server on http://{host}:{port}")
    uvicorn.run("server:app", host=host, port=port, reload=False)
