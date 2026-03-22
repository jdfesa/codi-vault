import asyncio
from facilito.async_api import AsyncFacilito

async def main():
    async with AsyncFacilito(headless=False) as client:
        print("Logged in: ", client.authenticated)
        page = await client.page
        await page.goto("https://codigofacilito.com/videos/bienvenida-al-curso-fbec4c96-1d85-49f8-b5ef-0e6f9a39b4dd")
        await page.wait_for_timeout(15000)
        content = await page.content()
        with open("page.html", "w") as f:
            f.write(content)
        print("Saved to page.html")

if __name__ == "__main__":
    asyncio.run(main())
