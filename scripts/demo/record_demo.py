#!/usr/bin/env python3
"""Record a narrated demo of the CritMatch /demo route.

Pipeline:
  1. Generate per-scene narration WAVs with edge-tts.
  2. Drive the /demo page with Playwright, advancing scenes in lock-step
     with each narration's measured duration.
  3. Concat the per-scene videos and mux the concatenated narration.

Output: scripts/demo/demo.mp4
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

import edge_tts
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:3000"
OUT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = OUT_DIR / "audio"
VIDEO_DIR = OUT_DIR / "video"
VOICE = "en-US-AriaNeural"
VIEWPORT = {"width": 1280, "height": 800}

# Each scene: id, narration, an action callback (executed after navigation),
# and a minimum duration floor in seconds (in case TTS comes back short).
SCENES = [
    {
        "id": "01_home",
        "url": "/",
        "text": (
            "This is CritMatch — a clinical trial cohort matching platform that "
            "pulls candidates straight from your EHR. Let's take a quick tour, "
            "starting with the public demo that needs no sign-in."
        ),
        "min_seconds": 8.0,
    },
    {
        "id": "02_demo_intro",
        "url": "/demo",
        "text": (
            "The demo route ships with eight bundled patient records and three "
            "ready-to-run trial presets. Everything runs in your browser — "
            "nothing is sent to a server."
        ),
        "min_seconds": 8.0,
    },
    {
        "id": "03_preset_oncology",
        "url": "/demo",
        "text": (
            "Let's swap to the oncology preset. The criteria form fills in "
            "automatically — required diagnoses, age range, exclusion drugs, "
            "and lab thresholds all come pre-loaded."
        ),
        "min_seconds": 9.0,
        "action": "preset_oncology",
    },
    {
        "id": "04_preset_hf",
        "url": "/demo",
        "text": (
            "Now back to heart failure plus diabetes. Hit Run Match and the "
            "engine scores every patient against the criteria in milliseconds."
        ),
        "min_seconds": 8.0,
        "action": "run_hf",
    },
    {
        "id": "05_results",
        "url": "/demo",
        "text": (
            "Each candidate gets a confidence badge — high, moderate, low, "
            "or excluded — along with the exact criteria they matched, the "
            "exclusion flags that fired, and any missing lab data."
        ),
        "min_seconds": 10.0,
        "action": "show_results",
    },
    {
        "id": "06_candidates_filter",
        "url": "/demo",
        "text": (
            "Filter to candidates only to focus on the high and moderate "
            "matches — the patients you'd actually approach for screening."
        ),
        "min_seconds": 7.0,
        "action": "filter_candidates",
    },
    {
        "id": "07_outro",
        "url": "/",
        "text": (
            "When you're ready for the real workflow, sign in and jump into "
            "the cohort builder, EDC export, and audit trail. Thanks for "
            "watching CritMatch."
        ),
        "min_seconds": 8.0,
    },
]


# ---------- TTS ----------

async def synth_one(text: str, out_path: Path) -> None:
    communicator = edge_tts.Communicate(text, VOICE)
    await communicator.save(str(out_path))


async def synth_all() -> None:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        out = AUDIO_DIR / f"{scene['id']}.mp3"
        if not out.exists():
            print(f"[tts] {scene['id']}")
            await synth_one(scene["text"], out)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


# ---------- Playwright actions ----------

def do_action(page, name: str) -> None:
    if name == "preset_oncology":
        page.get_by_role("button", name="Oncology").click()
        page.wait_for_timeout(800)
    elif name == "run_hf":
        page.get_by_role("button", name="Heart Failure + Diabetes").click()
        page.wait_for_timeout(600)
        page.get_by_role("button", name="Run Match").click()
        page.wait_for_timeout(800)
    elif name == "show_results":
        page.get_by_role("button", name="Heart Failure + Diabetes").click()
        page.wait_for_timeout(400)
        page.get_by_role("button", name="Run Match").click()
        page.wait_for_timeout(800)
        # Scroll the results panel into view, then a slow scroll.
        page.evaluate("window.scrollTo({ top: 500, behavior: 'smooth' })")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo({ top: 1000, behavior: 'smooth' })")
    elif name == "filter_candidates":
        page.get_by_role("button", name="Heart Failure + Diabetes").click()
        page.wait_for_timeout(400)
        page.get_by_role("button", name="Run Match").click()
        page.wait_for_timeout(800)
        page.evaluate("window.scrollTo({ top: 350, behavior: 'smooth' })")
        page.wait_for_timeout(500)
        page.get_by_role("button", name="Candidates only").first.click()
        page.wait_for_timeout(800)
        page.evaluate("window.scrollTo({ top: 700, behavior: 'smooth' })")


# ---------- Recording ----------

def record_scenes(scene_durations: dict[str, float]) -> list[Path]:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    produced: list[Path] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        for scene in SCENES:
            sid = scene["id"]
            duration = max(scene["min_seconds"], scene_durations[sid] + 0.4)
            print(f"[rec] {sid} -> {duration:.2f}s")
            ctx = browser.new_context(
                viewport=VIEWPORT,
                record_video_dir=str(VIDEO_DIR / sid),
                record_video_size=VIEWPORT,
            )
            page = ctx.new_page()
            page.goto(BASE_URL + scene["url"], wait_until="networkidle")
            page.wait_for_timeout(600)
            if scene.get("action"):
                do_action(page, scene["action"])
            # Hold on the final frame for the rest of the narration.
            page.wait_for_timeout(int(duration * 1000))
            video = page.video
            ctx.close()
            assert video is not None
            raw_path = Path(video.path())
            target = VIDEO_DIR / f"{sid}.webm"
            shutil.move(str(raw_path), target)
            produced.append(target)
        browser.close()
    return produced


# ---------- ffmpeg stitching ----------

def trim_to_duration(src: Path, seconds: float, dst: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src), "-t", f"{seconds:.3f}",
            "-r", "30", "-vf", f"scale={VIEWPORT['width']}:{VIEWPORT['height']}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-crf", "22", "-an", str(dst),
        ],
        check=True, capture_output=True,
    )


def concat_video(parts: list[Path], dst: Path) -> None:
    list_file = dst.parent / "concat.txt"
    list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(dst)],
        check=True, capture_output=True,
    )


def concat_audio(parts: list[Path], dst: Path) -> None:
    list_file = dst.parent / "concat_audio.txt"
    list_file.write_text("\n".join(f"file '{p.as_posix()}'" for p in parts) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c:a", "aac", "-b:a", "160k", str(dst)],
        check=True, capture_output=True,
    )


def mux(video: Path, audio: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video), "-i", str(audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", str(dst)],
        check=True, capture_output=True,
    )


def main() -> None:
    asyncio.run(synth_all())
    durations = {s["id"]: probe_duration(AUDIO_DIR / f"{s['id']}.mp3") for s in SCENES}
    print("[durations]", json.dumps(durations, indent=2))

    raw_videos = record_scenes(durations)

    trimmed_dir = OUT_DIR / "trimmed"
    trimmed_dir.mkdir(exist_ok=True)
    trimmed: list[Path] = []
    for scene, raw in zip(SCENES, raw_videos):
        sid = scene["id"]
        seconds = max(scene["min_seconds"], durations[sid] + 0.4)
        out = trimmed_dir / f"{sid}.mp4"
        trim_to_duration(raw, seconds, out)
        trimmed.append(out)

    video_only = OUT_DIR / "video_only.mp4"
    audio_full = OUT_DIR / "audio_full.m4a"
    final = OUT_DIR / "demo.mp4"

    concat_video(trimmed, video_only)
    concat_audio([AUDIO_DIR / f"{s['id']}.mp3" for s in SCENES], audio_full)
    mux(video_only, audio_full, final)
    print(f"[done] {final}")


if __name__ == "__main__":
    main()
