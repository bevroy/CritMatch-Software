"""Record one webm video per scene against a running Next.js dev server."""
import asyncio
import os
import sys
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
from scenes import SCENES  # noqa: E402

BASE_URL = os.environ.get("CM_BASE_URL", "http://localhost:3000")
OUT_DIR = Path(__file__).parent / "build" / "video"
VIEWPORT = {"width": 1280, "height": 800}


def audio_seconds(audio_path: Path) -> float:
    if not audio_path.exists():
        return 0.0
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path),
        ],
        text=True,
    ).strip()
    return float(out) if out else 0.0


async def run_action(page, action):
    kind = action["kind"]
    if kind == "wait_ms":
        await page.wait_for_timeout(action["ms"])
    elif kind == "wait":
        await page.wait_for_selector(action["selector"], timeout=action.get("timeout", 5000))
    elif kind == "click_text":
        loc = page.get_by_text(action["text"], exact=False).first
        await loc.scroll_into_view_if_needed()
        await loc.click()
    elif kind == "scroll_to_text":
        loc = page.get_by_text(action["text"], exact=False).first
        await loc.scroll_into_view_if_needed()
    elif kind == "scroll_to_top":
        await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    elif kind == "scroll_by":
        await page.evaluate(f"window.scrollBy({{top: {action['y']}, behavior: 'smooth'}})")
    else:
        raise ValueError(f"unknown action kind: {kind}")


async def record_scene(browser, scene, audio_dir: Path) -> Path:
    target_seconds = max(scene["duration"], audio_seconds(audio_dir / f"{scene['id']}.mp3") + 1.0)
    print(f"[{scene['id']}] target {target_seconds:.1f}s")

    context = await browser.new_context(
        viewport=VIEWPORT,
        record_video_dir=str(OUT_DIR / scene["id"]),
        record_video_size=VIEWPORT,
    )
    page = await context.new_page()
    if scene.get("url"):
        await page.goto(BASE_URL + scene["url"], wait_until="networkidle")
    elif RECORD_STATE["last_page"] is not None:
        # carry over previous page by reusing same URL
        await page.goto(RECORD_STATE["last_url"], wait_until="networkidle")
    await page.wait_for_timeout(800)

    start = asyncio.get_event_loop().time()
    for action in scene["actions"]:
        try:
            await run_action(page, action)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! action {action} failed: {exc}")

    elapsed = asyncio.get_event_loop().time() - start
    remaining_ms = int(max(0.0, target_seconds - elapsed) * 1000)
    if remaining_ms > 0:
        await page.wait_for_timeout(remaining_ms)

    RECORD_STATE["last_url"] = page.url
    RECORD_STATE["last_page"] = scene["id"]

    await context.close()
    # Playwright writes <random>.webm into scene dir
    written = list((OUT_DIR / scene["id"]).glob("*.webm"))
    if not written:
        raise RuntimeError(f"no video written for {scene['id']}")
    return written[0]


RECORD_STATE = {"last_url": None, "last_page": None}


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_dir = Path(__file__).parent / "build" / "audio"
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        for scene in SCENES:
            await record_scene(browser, scene, audio_dir)
        await browser.close()
    print("Recording complete.")


if __name__ == "__main__":
    asyncio.run(main())
