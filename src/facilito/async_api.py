from pathlib import Path

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from . import collectors
from .constants import LOGIN_URL, SESSION_FILE
from .errors import LoginError
from .helpers import read_json
from .logger import logger
from .utils import (
    load_state,
    login_required,
    normalize_cookies,
    save_state,
    try_except_request,
)


class AsyncFacilito:
    def __init__(self, headless=False):
        self.headless = headless
        self.authenticated = False

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            is_mobile=True,
            java_script_enabled=True,
        )

        stealth = Stealth(init_scripts_only=True)

        await stealth.apply_stealth_async(self._context)

        await load_state(self._context, SESSION_FILE)

        await self._set_profile()

        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._context.close()
        await self._browser.close()
        await self._playwright.stop()

    @property
    def context(self) -> BrowserContext:
        return self._context

    @property
    async def page(self) -> Page:
        return await self._context.new_page()

    @try_except_request
    async def login(self):
        logger.info("Opening browser — please log in manually.")
        logger.info("You have 3 minutes to complete the login.")

        AUTH_COOKIE_NAMES = {"remember_user_token"}

        try:
            page = await self.page
            await page.goto(LOGIN_URL)

            # Wait until one of the auth cookies appears (max 3 minutes)
            timeout = 3 * 60 * 1000  # 3 minutes in ms
            elapsed = 0
            interval = 2000  # check every 2 seconds

            while elapsed < timeout:
                await page.wait_for_timeout(interval)
                elapsed += interval

                cookies = await self._context.cookies()
                auth_cookies = [
                    c for c in cookies
                    if c.get("name") in AUTH_COOKIE_NAMES and c.get("value")
                ]

                if auth_cookies:
                    self.authenticated = True
                    await save_state(self.context, SESSION_FILE)
                    logger.info("Logged in successfully ✓")
                    break
            else:
                raise LoginError()

        except LoginError:
            raise
        except Exception:
            raise LoginError()

        finally:
            await page.close()

    @try_except_request
    async def logout(self):
        SESSION_FILE.unlink(missing_ok=True)
        logger.info("Logged out successfully")

    @try_except_request
    @login_required
    async def fetch_unit(self, url: str):
        return await collectors.fetch_unit(self.context, url)

    @try_except_request
    @login_required
    async def fetch_course(self, url: str):
        return await collectors.fetch_course(self.context, url)

    @try_except_request
    @login_required
    async def fetch_bootcamp(self, url: str):
        return await collectors.fetch_bootcamp(self.context, url)

    @try_except_request
    @login_required
    async def download(self, url: str, **kwargs):
        from pathlib import Path

        from .downloaders import download_bootcamp, download_course, download_unit
        from .models import TypeUnit
        from .utils import is_bootcamp, is_course, is_lecture, is_quiz, is_video

        if is_video(url) or is_lecture(url) or is_quiz(url):
            from .constants import APP_NAME
            unit = await self.fetch_unit(url)
            if unit:
                if getattr(unit, "parent_course_url", None):
                    logger.info(f"Video belongs to a course! Redirecting to course download: {unit.parent_course_url}")
                    course = await self.fetch_course(unit.parent_course_url)
                    await download_course(self.context, course, **kwargs)
                    return

                extension = ".mp4" if unit.type == TypeUnit.VIDEO else ".mhtml"
                save_path = Path(APP_NAME) / "Videos Sueltos" / (unit.slug + extension)
                await download_unit(
                    self.context,
                    unit,
                    save_path,
                    **kwargs,
                )

        elif is_course(url):
            course = await self.fetch_course(url)
            await download_course(self.context, course, **kwargs)

        elif is_bootcamp(url):
            bootcamp = await self.fetch_bootcamp(url)
            await download_bootcamp(self.context, bootcamp, **kwargs)

        else:
            raise Exception(
                "Please provide a valid URL, either a video, lecture, "
                "course, or bootcamp."
            )

    @try_except_request
    async def set_cookies(self, path: Path):
        cookies = normalize_cookies(read_json(path))  # type: ignore
        await self.context.add_cookies(cookies)  # type: ignore
        await self._set_profile()
        await save_state(self.context, SESSION_FILE)

    @try_except_request
    async def _set_profile(self):
        """
        Detects if the user is authenticated by checking for session cookies.
        This approach is resilient to HTML changes on the website.
        """
        AUTH_COOKIE_NAMES = {"remember_user_token"}

        try:
            cookies = await self._context.cookies()
            auth_cookies = [
                c for c in cookies if c.get("name") in AUTH_COOKIE_NAMES and c.get("value")
            ]

            if auth_cookies:
                self.authenticated = True
                logger.info("Session restored from cookies ✓")
            else:
                logger.info("No active session found. Run: facilito login")

        except Exception:
            pass
