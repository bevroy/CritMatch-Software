"""Combine per-scene videos with their narration tracks into a single MP4."""
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from scenes import SCENES  # noqa: E402

ROOT = Path(__file__).parent / "build"
SCENE_OUT = ROOT / "scenes"
SCENE_OUT.mkdir(parents=True, exist_ok=True)
FINAL = Path(__file__).parent / "build" / "critmatch-demo.mp4"


def run(cmd: str) -> None:
    print(">", cmd)
    subprocess.check_call(shlex.split(cmd))


def first_webm(scene_id: str) -> Path:
    matches = list((ROOT / "video" / scene_id).glob("*.webm"))
    if not matches:
        raise FileNotFoundError(f"no webm for {scene_id}")
    return matches[0]


def stitch_scene(scene) -> Path:
    sid = scene["id"]
    video = first_webm(sid)
    audio = ROOT / "audio" / f"{sid}.mp3"
    out = SCENE_OUT / f"{sid}.mp4"
    # Pad audio with silence so it matches the (often longer) video; -shortest cuts to shorter stream.
    # We use -shortest so video length == min(video, padded audio); we padded audio with apad
    # so it never ends first.
    cmd = (
        f"ffmpeg -y -loglevel error "
        f"-i {video} "
        f"-i {audio} "
        f"-filter_complex \"[1:a]apad[a1]\" "
        f"-map 0:v -map [a1] "
        f"-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "
        f"-c:a aac -b:a 160k -ar 44100 "
        f"-shortest "
        f"{out}"
    )
    print(">", cmd)
    subprocess.check_call(cmd, shell=True)
    return out


def main() -> None:
    parts = [stitch_scene(s) for s in SCENES]
    list_file = ROOT / "concat.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in parts) + "\n")
    run(
        f"ffmpeg -y -loglevel error -f concat -safe 0 "
        f"-i {list_file} -c copy {FINAL}"
    )
    print(f"\nFinal video: {FINAL}")


if __name__ == "__main__":
    main()
