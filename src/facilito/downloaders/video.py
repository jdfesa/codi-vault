import functools
import shutil
from pathlib import Path

from ..logger import logger
from ..models import Quality

TMP_DIR_PATH = Path("Facilito") / ".tmp"
TMP_DIR_PATH.mkdir(parents=True, exist_ok=True)


def ffmpeg_required(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        if not shutil.which("ffmpeg"):
            logger.error("ffmpeg is not installed. Install it with: brew install ffmpeg")
            return
        return await func(*args, **kwargs)

    return wrapper


@ffmpeg_required
async def download_video(
    url: str,
    path: Path,
    quality: Quality = Quality.MAX,
    **kwargs,
):
    """
    Download a video from a HLS m3u8 URL using ffmpeg with authenticated cookies.

    :param str url: URL of the m3u8 playlist.
    :param Path path: Path to save the video (.mp4).
    :param Quality quality: Kept for API compatibility (ffmpeg picks best available).
    :param list[dict] cookies: Playwright cookies for authentication (default: None).
    :param bool override: Override existing file if exists (default: False).
    :param int threads: Number of threads to use (default: 10).
    """
    import subprocess

    cookies: list[dict] = kwargs.get("cookies", None) or []
    override: bool = kwargs.get("override", False)
    threads: int = kwargs.get("threads", 10)

    path.parent.mkdir(parents=True, exist_ok=True)

    if not override and path.exists():
        logger.info(f"[{path.name}] already exists, skipping.")
        return

    # Build cookie header string from Playwright session cookies
    cookie_parts = [
        f"{c['name']}={c['value']}"
        for c in cookies
        if any(
            domain in c.get("domain", "")
            for domain in ["codigofacilito", "video-storage"]
        )
    ]
    cookie_str = "; ".join(cookie_parts)

    user_agent = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # Build ffmpeg headers block (all in one -headers flag to avoid empty arg issues)
    headers = f"User-Agent: {user_agent}\r\n"
    if cookie_str:
        headers += f"Cookie: {cookie_str}\r\n"

    command = [
        "ffmpeg",
        "-loglevel", "warning",
        "-stats",
        "-headers", headers,
        "-i", url,
        "-c", "copy",
        "-threads", str(threads),
        "-bsf:a", "aac_adtstoasc",
    ]

    if override:
        command += ["-y"]
    else:
        command += ["-n"]

    command.append(path.as_posix())

    logger.info(f"Downloading [{path.name}]...")

    try:
        result = subprocess.run(command)
        if result.returncode == 0:
            logger.info(f"[{path.name}] downloaded successfully ✓")
        else:
            logger.error(
                f"Error downloading [{path.name}] (ffmpeg exit code {result.returncode})"
            )
    except Exception:
        logger.exception(f"Error downloading [{path.name}]")
