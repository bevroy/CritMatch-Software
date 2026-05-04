"""Generate per-scene narration MP3s using edge-tts (Microsoft AI voice)."""
import asyncio
import os
import sys
from pathlib import Path

import edge_tts

sys.path.insert(0, str(Path(__file__).parent))
from scenes import SCENES  # noqa: E402

VOICE = os.environ.get("CM_VOICE", "en-US-AriaNeural")
OUT_DIR = Path(__file__).parent / "build" / "audio"


async def synth_one(text: str, out_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate="+0%")
    await communicate.save(str(out_path))


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for scene in SCENES:
        out_path = OUT_DIR / f"{scene['id']}.mp3"
        print(f"  -> {out_path.name}")
        await synth_one(scene["narration"], out_path)
    print(f"Audio written to {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
