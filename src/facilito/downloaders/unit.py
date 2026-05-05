from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext

from ..collectors import fetch_video
from ..constants import APP_NAME
from ..logger import logger
from ..models import TypeUnit, Unit
from ..utils import save_page
from .video import download_video


def _normalize_media_slug(slug: str, *, strip_uuid: bool = True) -> str:
    import re

    slug = slug.replace("_", "-")
    slug = re.sub(r"^\d+-", "", slug)
    slug = re.sub(r"^clase-\d+-", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    if strip_uuid:
        slug = re.sub(
            r"-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            "",
            slug,
            flags=re.IGNORECASE,
        )

    return slug


def _can_reuse_by_title_slug(slug: str) -> bool:
    generic_slugs = {
        "introduccion",
        "introduccion-a-la-clase",
        "bienvenida",
        "presentacion",
    }
    return slug not in generic_slugs and len(slug) >= 12


def _unit_media_slugs(unit: Unit) -> tuple[set[str], set[str]]:
    url_slug = Path(urlsplit(unit.url).path).name

    strict_slugs = {
        normalized_slug
        for slug in (url_slug,)
        if (normalized_slug := _normalize_media_slug(slug, strip_uuid=False))
    }
    loose_slugs = {
        normalized_slug
        for slug in (unit.slug, url_slug)
        if (normalized_slug := _normalize_media_slug(slug))
        and _can_reuse_by_title_slug(normalized_slug)
    }

    return strict_slugs, loose_slugs


def _existing_video_path(unit: Unit, path: Path) -> Path | None:
    if path.exists() and path.stat().st_size > 0:
        return path

    strict_slugs, loose_slugs = _unit_media_slugs(unit)
    if not strict_slugs and not loose_slugs:
        return None

    app_path = Path(APP_NAME)
    if not app_path.exists():
        return None

    for candidate in app_path.rglob("*.mp4"):
        if (
            candidate == path
            or not candidate.is_file()
            or candidate.stat().st_size == 0
        ):
            continue

        strict_candidate_slug = _normalize_media_slug(candidate.stem, strip_uuid=False)
        loose_candidate_slug = _normalize_media_slug(candidate.stem)
        if strict_candidate_slug in strict_slugs or loose_candidate_slug in loose_slugs:
            return candidate

    return None


def _reuse_existing_video(existing_path: Path, path: Path) -> None:
    import os
    import shutil

    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        os.link(existing_path, path)
    except OSError:
        shutil.copy2(existing_path, path)

    logger.info(f"[{path.name}] reused from existing file: {existing_path}")


async def download_unit(context: BrowserContext, unit: Unit, path: Path, **kwargs):
    """
    Download a Unit.

    :param BrowserContext context: Playwright context.
    :param Unit unit: Unit model to download.
    :param Path path: Path to save the video.

    :param Quality quality: Quality of the video (default: Quality.MAX).
    :param bool override: Override existing file if exists (default: False).
    :param int threads: Number of threads to use (default: 10).
    """

    if unit.type == TypeUnit.VIDEO:
        override = kwargs.get("override", False)
        if not override:
            existing_path = _existing_video_path(unit, path)
            if existing_path:
                if existing_path == path:
                    logger.info(f"[{path.name}] already exists, skipping.")
                else:
                    _reuse_existing_video(existing_path, path)
                return

        video = await fetch_video(context, unit.url)
        await download_video(
            video.url,
            path=path,
            cookies=await context.cookies(),
            **kwargs,
        )  # type: ignore

    else:
        await save_page(context, unit.url, path)
