from playwright.async_api import BrowserContext

from ..errors import UnitError
from ..helpers import slugify
from ..models import TypeUnit, Unit
from ..utils import canonical_content_url, get_unit_type


async def fetch_unit(context: BrowserContext, url: str):
    NAME_SELECTOR = "h1"

    try:
        type = get_unit_type(url)

        if type == TypeUnit.QUIZ:
            # TODO: implement quiz fetching
            return Unit(
                type=type,
                url=url,
                name="quiz",
                slug="quiz",
            )
    except Exception as e:
        from ..logger import logger

        logger.error(f"Error getting unit type: {e}")
        raise UnitError()

    try:
        page = await context.new_page()
        await page.goto(url)

        name = await page.locator(NAME_SELECTOR).first.text_content()

        parent_course_url = None
        try:
            course_path = await page.locator("a[href^='/cursos/']").first.get_attribute(
                "href", timeout=1000
            )
            if course_path:
                parent_course_url = canonical_content_url(course_path)
        except Exception:
            pass

        if not name:
            raise UnitError()

        type = get_unit_type(url)

    except Exception as e:
        from ..logger import logger

        logger.error(f"Error fetching unit page: {e}")
        raise UnitError()

    finally:
        await page.close()

    return Unit(
        type=type,
        name=name,
        url=url,
        slug=slugify(name),
        parent_course_url=parent_course_url,
    )
