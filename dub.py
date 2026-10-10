#!/usr/bin/env python3
"""
CLI entry point for the Automated Video Dubbing System.
Usage:
    python dub.py "<YOUTUBE_URL>"
    python dub.py "<YOUTUBE_URL>" --model small --voice en-US-ChristopherNeural
"""

import sys
import argparse
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeElapsedColumn
)
from rich.panel import Panel

from backend.models import PipelineOptions
from backend.pipeline import run_pipeline
from backend.config import DEFAULT_WHISPER_MODEL, DEFAULT_TTS_VOICE
from backend.utils import format_duration

console = Console(force_terminal=True, legacy_windows=False)

STAGE_CONFIG = [
    ("download", "[1/6] Downloading video..."),
    ("transcribe", "[2/6] Transcribing with Whisper..."),
    ("translate", "[3/6] Translating to English with IndicTrans2..."),
    ("synthesize", "[4/6] Synthesizing English speech..."),
    ("align", "[5/6] Aligning audio..."),
    ("remix", "[6/6] Remuxing final video..."),
]

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Automated Video Dubbing System — Multilingual speech to naturally timed English dub."
    )
    parser.add_argument("url", help="YouTube video URL to dub into English")
    parser.add_argument(
        "--model",
        default=DEFAULT_WHISPER_MODEL,
        help=f"Whisper model size (default: {DEFAULT_WHISPER_MODEL})"
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_TTS_VOICE,
        help=f"Edge-TTS English voice (default: {DEFAULT_TTS_VOICE})"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-run and bypass previous stage caches"
    )

    args = parser.parse_args()

    console.print()
    console.print(
        Panel.fit(
            "[bold white]Automated Video Dubbing System[/bold white]\n"
            "[cyan]Multilingual Speech Recognition (Whisper)[/cyan] -> "
            "[magenta]IndicTrans2[/magenta] -> "
            "[green]Edge-TTS[/green] -> "
            "[yellow]FFmpeg Timing Alignment[/yellow]",
            border_style="bright_blue"
        )
    )
    console.print()

    options = PipelineOptions(
        whisper_model=args.model,
        tts_voice=args.voice,
        speed_adjustment=True
    )

    # Dictionary mapping stage names to progress task IDs
    task_map = {}

    with Progress(
        TextColumn("  {task.description:<48}"),
        BarColumn(bar_width=25, complete_style="green", finished_style="bold green"),
        TextColumn("[bold cyan]{task.percentage:>3.0f}%[/bold cyan]"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        # Pre-create all 6 stage bars
        for stage_key, label in STAGE_CONFIG:
            task_id = progress.add_task(label, total=100, completed=0)
            task_map[stage_key] = task_id

        current_active_stage = None

        def progress_callback(event: dict) -> None:
            nonlocal current_active_stage
            stage = event.get("stage")
            percent = event.get("percent", 0)

            # Map sub-stages like extract_audio to transcribe
            if stage == "extract_audio":
                stage = "transcribe"

            if stage in task_map:
                tid = task_map[stage]
                progress.update(tid, completed=percent)

                # If this stage finished (100%), mark previous stages 100% as well
                if percent >= 100:
                    for prev_stage, _ in STAGE_CONFIG:
                        if prev_stage == stage:
                            break
                        prev_tid = task_map[prev_stage]
                        progress.update(prev_tid, completed=100)

        try:
            result = run_pipeline(
                url=args.url,
                options=options,
                on_progress=progress_callback,
                force_restart=args.force
            )
            # Ensure all bars are 100% complete
            for tid in task_map.values():
                progress.update(tid, completed=100)

        except KeyboardInterrupt:
            console.print("\n[bold red]Dubbing process interrupted by user.[/bold red]")
            return 130
        except Exception as e:
            console.print(f"\n[bold red]Pipeline Error:[/bold red] {str(e)}")
            return 1

    console.print()
    console.print("[bold green]Completed.[/bold green]")
    console.print()
    console.print(f"[bold]Output:[/bold]\n[cyan]{result['artifacts']['final_dubbed']}[/cyan]")
    console.print()
    console.print(f"[bold]Source Language:[/bold] {result.get('source_language', 'unknown')}")
    console.print(f"[bold]Video Duration:[/bold]  {result.get('duration_formatted', 'unknown')}")
    console.print(f"[bold]Total Processing Time:[/bold] {result.get('total_processing_formatted', 'unknown')}")
    console.print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
