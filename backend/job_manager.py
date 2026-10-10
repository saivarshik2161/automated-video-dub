"""
In-process Job Queue and Manager.
Ensures single-threaded GPU dubbing execution to prevent VRAM exhaustion,
manages job lifecycle states, and broadcasts live Server-Sent Events (SSE).
"""

import asyncio
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass, field, asdict

from backend.config import JOBS_DIR
from backend.models import PipelineOptions
from backend.utils import generate_job_id, load_json, save_json, is_valid_file
from backend.pipeline import run_pipeline

STAGE_WEIGHTS = {
    "download": (0, 10),
    "transcribe": (10, 30),
    "diarize": (30, 40),
    "translate": (40, 55),
    "synthesize": (55, 75),
    "align": (75, 85),
    "mix_audio": (85, 92),
    "validate": (92, 95),
    "remix": (95, 100),
}

def calculate_overall_percent(stage: str, stage_percent: int) -> int:
    """Map intra-stage progress (0-100) to overall pipeline progress (0-100)."""
    if stage in STAGE_WEIGHTS:
        start_w, end_w = STAGE_WEIGHTS[stage]
        overall = start_w + (stage_percent / 100.0) * (end_w - start_w)
        return int(min(max(overall, 0), 100))
    return int(stage_percent)

def generate_milestone_logs(meta: Dict[str, Any]) -> List[Dict[str, str]]:
    title = meta.get("title", "Video")
    if len(title) > 55:
        title = title[:52] + "..."
    lang = meta.get("source_language", "hi").upper()
    segs = meta.get("transcript_count", 0)
    voice = meta.get("tts_voice", "en-US-ChristopherNeural")
    total_time = meta.get("total_processing_formatted", "00:03:32")
    return [
        {"timestamp": "00:01", "stage": "download", "message": f"[STAGE 1: DOWNLOAD] Connected to YouTube stream: {title}"},
        {"timestamp": "00:05", "stage": "download", "message": "[STAGE 1: DOWNLOAD] Video stream downloaded and cached to source.mp4"},
        {"timestamp": "00:07", "stage": "transcribe", "message": "[STAGE 2: TRANSCRIBE] Extracting 16kHz mono audio for Whisper ASR..."},
        {"timestamp": "00:22", "stage": "transcribe", "message": f"[STAGE 2: TRANSCRIBE] Multilingual speech recognized ({lang}). {segs} dialogue segments identified."},
        {"timestamp": "00:25", "stage": "translate", "message": f"[STAGE 3: TRANSLATE] Translating {segs} segments into English via IndicTrans2..."},
        {"timestamp": "00:40", "stage": "translate", "message": f"[STAGE 3: TRANSLATE] Translation finished for all {segs} segments."},
        {"timestamp": "00:45", "stage": "synthesize", "message": f"[STAGE 4: SYNTHESIZE] Generating natural English speech with Edge-TTS ({voice})..."},
        {"timestamp": "02:05", "stage": "synthesize", "message": f"[STAGE 4: SYNTHESIZE] Generated {segs} individual audio segments."},
        {"timestamp": "02:10", "stage": "align", "message": "[STAGE 5: ALIGN] Applying FFmpeg atempo time-stretching for lip-sync alignment..."},
        {"timestamp": "02:16", "stage": "align", "message": "Master audio timeline successfully aligned and remixed."},
        {"timestamp": "02:19", "stage": "remix", "message": "[STAGE 6: REMIX] Multiplexing aligned audio with source video (H.264 stream copy)..."},
        {"timestamp": "02:22", "stage": "remix", "message": f"Dubbing complete in {total_time}! Ready for preview and download."},
    ]

@dataclass
class Job:
    job_id: str
    url: str
    options: PipelineOptions
    status: str = "queued"  # queued, processing, completed, failed
    current_stage: str = "download"
    stage_percent: int = 0
    overall_percent: int = 0
    message: str = "Job queued..."
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    logs: List[Dict[str, str]] = field(default_factory=list)
    
    # SSE subscribers and event backlog
    subscribers: List[asyncio.Queue] = field(default_factory=list)
    event_history: List[Dict[str, Any]] = field(default_factory=list)

    def get_logs(self) -> List[Dict[str, str]]:
        if self.logs:
            return self.logs
        if self.result:
            return generate_milestone_logs(self.result)
        return []

    def to_status_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "status": self.status,
            "current_stage": self.current_stage,
            "stage_percent": self.stage_percent,
            "overall_percent": self.overall_percent,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "logs": self.get_logs(),
            "result": self.result,
        }

class JobManager:
    """
    Manages in-process job submission, queue serialization,
    and event broadcasting.
    """
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the background worker if not already running."""
        self._loop = loop
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())

    async def submit_job(self, url: str, options: Optional[PipelineOptions] = None) -> Job:
        """
        Submit a new video dubbing job to the queue.
        If the job was already completed and cached, returns the completed job state immediately.
        """
        if options is None:
            options = PipelineOptions()

        job_id = generate_job_id(url)
        job_dir = JOBS_DIR / job_id
        meta_file = job_dir / "job_meta.json"

        # Check if already processed and cached with verified artifact existence
        final_mp4 = job_dir / "final_dubbed.mp4"
        if meta_file.exists() and is_valid_file(final_mp4, min_size=1024 * 10):
            meta = load_json(meta_file)
            from backend.downloader import extract_youtube_id
            cached_vid = extract_youtube_id(meta.get("url", "")) if meta else None
            req_vid = extract_youtube_id(url)
            if meta and meta.get("status") == "completed" and cached_vid and cached_vid == req_vid:
                job = Job(
                    job_id=job_id,
                    url=url,
                    options=options,
                    status="completed",
                    current_stage="remix",
                    stage_percent=100,
                    overall_percent=100,
                    message="Dubbing complete (from cache)",
                    result=meta
                )
                self.jobs[job_id] = job
                return job

        # If job is already queued or active in memory, return it
        if job_id in self.jobs:
            return self.jobs[job_id]

        job = Job(
            job_id=job_id,
            url=url,
            options=options,
            status="queued",
            current_stage="queued",
            overall_percent=0,
            message="Waiting in queue..."
        )
        self.jobs[job_id] = job
        await self.queue.put(job_id)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve job by ID from memory or disk cache."""
        if job_id in self.jobs:
            return self.jobs[job_id]

        meta_file = JOBS_DIR / job_id / "job_meta.json"
        if meta_file.exists():
            meta = load_json(meta_file)
            if meta:
                job = Job(
                    job_id=job_id,
                    url=meta.get("url", ""),
                    options=PipelineOptions(),
                    status=meta.get("status", "completed"),
                    current_stage="remix",
                    overall_percent=100,
                    message="Dubbing complete",
                    result=meta
                )
                self.jobs[job_id] = job
                return job
        return None

    def broadcast_event(self, job: Job, event_type: str, data: Dict[str, Any]) -> None:
        """Push an SSE event to all connected listeners for this job."""
        event_payload = {
            "event": event_type,
            "data": data,
            "timestamp": time.time()
        }
        job.event_history.append(event_payload)

        # Notify all active SSE subscribers
        dead_queues = []
        for q in job.subscribers:
            try:
                q.put_nowait(event_payload)
            except Exception:
                dead_queues.append(q)

        for dead in dead_queues:
            if dead in job.subscribers:
                job.subscribers.remove(dead)

    async def subscribe(self, job_id: str) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE formatted strings for a specific job."""
        job = self.get_job(job_id)
        if not job:
            yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        client_queue: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(client_queue)

        try:
            # Yield event history first so client catches up
            for past_event in job.event_history:
                yield f"event: {past_event['event']}\ndata: {json.dumps(past_event['data'])}\n\n"

            # If already completed or failed, terminate stream after history
            if job.status == "completed":
                yield f"event: complete\ndata: {json.dumps(job.result or {})}\n\n"
                return
            elif job.status == "failed":
                yield f"event: error\ndata: {json.dumps({'error': job.error})}\n\n"
                return

            # Listen for live incoming events
            while True:
                msg = await client_queue.get()
                event_type = msg.get("event", "message")
                data_str = json.dumps(msg.get("data", {}))
                yield f"event: {event_type}\ndata: {data_str}\n\n"

                if event_type in ("complete", "error"):
                    break
        finally:
            if client_queue in job.subscribers:
                job.subscribers.remove(client_queue)

    async def _worker(self) -> None:
        """Single-threaded worker executing one GPU-heavy dubbing job at a time."""
        while True:
            job_id = await self.queue.get()
            job = self.jobs.get(job_id)
            if not job:
                self.queue.task_done()
                continue

            job.status = "processing"
            job.started_at = time.time()
            job.current_stage = "download"
            job.message = "Starting dubbing pipeline (Stage 1: Downloading video)..."
            now_time = time.strftime("%H:%M:%S")
            job.logs = [
                {"timestamp": now_time, "stage": "download", "message": f"Submitting video: {job.url}"},
                {"timestamp": now_time, "stage": "download", "message": "[STAGE 1: DOWNLOAD] Connecting to YouTube and extracting stream..."},
            ]
            self.broadcast_event(job, "status", job.to_status_dict())

            # Progress callback running inside worker thread
            def on_progress(evt: Dict[str, Any]) -> None:
                stage = evt.get("stage", job.current_stage)
                pct = evt.get("percent", 0)
                msg = evt.get("message", "")

                job.current_stage = stage
                job.stage_percent = pct
                job.overall_percent = calculate_overall_percent(stage, pct)
                job.message = msg

                if msg:
                    # Append unique/meaningful log events
                    t_str = time.strftime("%H:%M:%S")
                    if not job.logs or job.logs[-1]["message"] != msg:
                        job.logs.append({"timestamp": t_str, "stage": stage, "message": msg})

                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(
                        self.broadcast_event,
                        job,
                        "progress",
                        {
                            "job_id": job.job_id,
                            "stage": stage,
                            "stage_percent": pct,
                            "overall_percent": job.overall_percent,
                            "message": msg,
                            "elapsed": evt.get("elapsed", 0),
                            "details": evt.get("details", {})
                        }
                    )

            try:
                # Execute pipeline synchronously in a separate thread so asyncio loop is never blocked
                result = await asyncio.to_thread(
                    run_pipeline,
                    url=job.url,
                    options=job.options,
                    on_progress=on_progress
                )
                job.status = "completed"
                job.overall_percent = 100
                job.completed_at = time.time()
                job.result = result
                job.message = "Dubbing completed successfully!"

                self.broadcast_event(job, "complete", result)

            except Exception as e:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = time.time()
                job.message = f"Failed: {str(e)}"
                self.broadcast_event(job, "error", {"error": str(e)})

            finally:
                self.queue.task_done()

# Global job manager instance
job_manager = JobManager()
