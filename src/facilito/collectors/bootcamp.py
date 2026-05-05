import asyncio
import re

from playwright.async_api import BrowserContext, Page

from ..errors import CourseError, UnitError
from ..helpers import slugify
from ..logger import logger
from ..models import Bootcamp, Module, Unit
from ..utils import ensure_absolute_url, get_unit_type


def _clean_text(text: str) -> str:
    text = " ".join(text.strip().split())
    return re.sub(r"^Clase\s+\d+\s+", "", text)


async def _get_link_title(link, fallback: str | None = None) -> str | None:
    for selector in ("p.ibm.f-text-16", "p.ibm", ".ibm"):
        try:
            title = await link.locator(selector).first.text_content(timeout=500)
        except Exception:
            continue

        if title:
            return _clean_text(title)

    try:
        title = await link.inner_text(timeout=1000)
    except Exception:
        return fallback

    if not title:
        return fallback

    title = _clean_text(title)
    for prefix in ("done_all ", "check_circle_outline "):
        if title.startswith(prefix):
            title = title[len(prefix) :]

    return title or fallback


async def _extract_current_item_units(page: Page) -> list[Unit]:
    """
    Extract the units visible in a course/block player page.

    Program entries point to /cursos/... pages. Some of those pages are complete
    mini-courses or course blocks, so the final redirected video URL is not
    enough; the expanded player sidebar contains the actual units to download.
    """
    UNIT_LINKS_SELECTOR = ".collapsible-body ul a[href]"

    unit_links = page.locator(UNIT_LINKS_SELECTOR)
    units_count = await unit_links.count()

    units: list[Unit] = []
    seen_urls: set[str] = set()

    for i in range(units_count):
        unit_link = unit_links.nth(i)
        unit_url = await unit_link.get_attribute("href")

        if not unit_url:
            continue

        full_url = ensure_absolute_url(unit_url)

        try:
            unit_type = get_unit_type(full_url)
        except UnitError:
            continue

        if full_url in seen_urls:
            continue

        unit_name = await _get_link_title(unit_link)
        if not unit_name:
            continue

        seen_urls.add(full_url)
        units.append(
            Unit(
                type=unit_type,
                name=unit_name,
                slug=slugify(unit_name),
                url=full_url,
            )
        )

    return units


async def _fetch_bootcamp_item_units(
    context: BrowserContext,
    url: str,
    fallback_name: str,
) -> list[Unit]:
    page = await context.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

        units = await _extract_current_item_units(page)
        if units:
            return units

        final_url = page.url
        unit_type = get_unit_type(final_url)
        return [
            Unit(
                type=unit_type,
                name=fallback_name,
                slug=slugify(fallback_name),
                url=final_url,
            )
        ]

    except Exception as exc:
        logger.debug(f"Could not parse bootcamp item {url}: {exc}")
        return []

    finally:
        await page.close()


async def _fetch_bootcamp_modules(page: Page) -> list[Module]:
    """
    Fetch all modules from a bootcamp page.

    Bootcamp structure:
    - Each module is collapsible section (Módulo 1, Módulo 2, etc.)
    - Each module contains multiple classes/units
    - Units can be videos, lectures, or quizzes
    """
    # Top-level modules from the program page. Nested units are resolved by
    # opening each course/block entry individually.
    MODULES_SELECTOR = "ul.collapsible.f-topics > li.f-radius-small"

    try:
        modules_selectors = page.locator(MODULES_SELECTOR)
        modules_count = await modules_selectors.count()

        if not modules_count:
            raise CourseError("No modules found in bootcamp")

        # Expand all modules to access their content
        for i in range(modules_count):
            CHEVRON_SELECTOR = ".collapsible-header"
            try:
                chevron = modules_selectors.nth(i).locator(CHEVRON_SELECTOR).first
                # Check if module is already expanded
                is_active = await modules_selectors.nth(i).get_attribute("class")
                if is_active and "active" not in is_active:
                    await chevron.click()
            except Exception:
                # Some modules might already be expanded or not clickable
                pass

        # Wait for content to load
        await asyncio.sleep(2)

        modules: list[Module] = []
        for i in range(modules_count):
            # Module name is in the header with class "f-green-text--2"
            MODULE_NAME_SELECTOR = ".collapsible-header span.f-green-text"
            UNITS_SELECTOR = ".collapsible-body ul a"

            # Get module name
            module_name_elem = (
                modules_selectors.nth(i).locator(MODULE_NAME_SELECTOR).first
            )
            module_name = await module_name_elem.text_content()

            if not module_name:
                # Try alternative selector
                MODULE_NAME_ALT_SELECTOR = ".collapsible-header h4"
                module_name = (
                    await modules_selectors.nth(i)
                    .locator(MODULE_NAME_ALT_SELECTOR)
                    .first.text_content()
                )
                if not module_name:
                    raise CourseError(
                        f"Could not extract module name for module {i + 1}"
                    )

            # Clean module name: remove newlines, extra spaces, and tabs
            module_name = " ".join(module_name.strip().split())

            # Get all program entries in this module. Entries can be direct
            # lessons, course blocks, or mini-courses with several units.
            item_locators = modules_selectors.nth(i).locator(UNITS_SELECTOR)
            items_count = await item_locators.count()

            if not items_count:
                # Module might be empty, skip it
                continue

            units: list[Unit] = []
            seen_unit_urls: set[str] = set()
            for j in range(items_count):
                item_link = item_locators.nth(j)
                item_name = await _get_link_title(item_link)
                item_url = await item_link.get_attribute("href")

                if not item_name or not item_url:
                    # Skip invalid units
                    continue

                item_units = await _fetch_bootcamp_item_units(
                    page.context,
                    ensure_absolute_url(item_url),
                    item_name,
                )
                for unit in item_units:
                    if unit.url in seen_unit_urls:
                        continue

                    seen_unit_urls.add(unit.url)
                    units.append(unit)

            if units:  # Only add module if it has valid units
                modules.append(
                    Module(
                        name=module_name,
                        slug=slugify(module_name),
                        units=units,
                    )
                )

    except Exception as e:
        raise UnitError(f"Error fetching bootcamp modules: {str(e)}")

    return modules


async def fetch_bootcamp(context: BrowserContext, url: str) -> Bootcamp:
    """
    Fetch all information from a bootcamp.

    Args:
        context: Playwright browser context
        url: URL of the bootcamp (e.g., https://codigofacilito.com/programas/ingles-conversacional)

    Returns:
        Bootcamp model with all modules and units

    Raises:
        CourseError: If bootcamp information cannot be extracted
    """
    # Selector for bootcamp title (similar to course)
    NAME_SELECTOR = ".f-course-presentation h1, .cover-with-image h1, h1.h1"

    try:
        page = await context.new_page()
        await page.goto(url)

        # Wait for page to load
        await asyncio.sleep(1)

        # Get bootcamp name
        name = await page.locator(NAME_SELECTOR).first.text_content()

        if not name:
            raise CourseError("Could not extract bootcamp name")

        # Clean bootcamp name: remove newlines, extra spaces, and tabs
        name = " ".join(name.strip().split())

        # Fetch all modules
        modules = await _fetch_bootcamp_modules(page)

        if not modules:
            raise CourseError("No modules found in bootcamp")

    except Exception as e:
        raise CourseError(f"Error fetching bootcamp: {str(e)}")

    finally:
        await page.close()

    return Bootcamp(
        name=name,
        slug=slugify(name),
        url=url,
        modules=modules,
    )
