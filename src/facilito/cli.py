import asyncio
from pathlib import Path

import typer
from typing_extensions import Annotated

from facilito import AsyncFacilito, Quality

app = typer.Typer(rich_markup_mode="rich")


@app.command()
def login():
    """
    Open a browser window to Login to Codigo Facilito.

    Usage:
        facilito login
    """
    asyncio.run(_login())


@app.command()
def set_cookies(
    path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            help="Path to cookies.json",
            show_default=False,
        ),
    ],
):
    """
    Login to Codigo Facilito using your cookies.

    Usage:
        facilito set-cookies cookies.json
    """
    asyncio.run(_set_cookies(path))


@app.command()
def logout():
    """
    Delete the Facilito session from the local storage.

    Usage:
        facilito logout
    """
    asyncio.run(_logout())


@app.command()
def download(
    url: Annotated[
        str,
        typer.Argument(
            help="The URL of the bootcamp | course | video | lecture to download.",
            show_default=False,
        ),
    ],
    quality: Annotated[
        Quality,
        typer.Option(
            "--quality",
            "-q",
            help="The quality of the video to download.",
            show_default=True,
        ),
    ] = Quality.MAX,
    override: Annotated[
        bool,
        typer.Option(
            "--override",
            "-w",
            help="Override existing file if exists.",
            show_default=True,
        ),
    ] = False,
    threads: Annotated[
        int,
        typer.Option(
            "--threads",
            "-t",
            min=1,
            max=16,
            help="Number of threads to use.",
            show_default=True,
        ),
    ] = 10,
    headless: Annotated[
        bool,
        typer.Option(
            "--headless/--no-headless",
            help="Run browser in headless (minimized/hidden) mode.",
            show_default=True,
        ),
    ] = True,
):
    """
    Download a bootcamp | course | video | lecture from the given URL.

    Arguments:
        url: str - The URL of the bootcamp, course, video, or lecture to download.

    Usage:
        facilito download <url>

    Examples:
        facilito download https://codigofacilito.com/programas/ingles-conversacional

        facilito download https://codigofacilito.com/cursos/docker

        facilito download https://codigofacilito.com/videos/...

        facilito download https://codigofacilito.com/articulos/...
    """
    asyncio.run(
        _download(
            url,
            quality=quality,
            override=override,
            threads=threads,
            headless=headless,
        )
    )


@app.command()
def interactive():
    """
    Start an interactive wizard to download content.

    Usage:
        facilito interactive
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, IntPrompt, Prompt

    console = Console()
    console.print(
        Panel.fit(
            "[bold white]Bienvenido al entorno interactivo de codi-vault[/bold white]",
            subtitle="Descarga guiada",
            border_style="cyan",
        )
    )

    url = Prompt.ask(
        "\n[bold cyan]1. URL del recurso[/bold cyan] (curso, bootcamp, video)"
    )
    if not url:
        console.print(
            "[bold red]❌ Debes proveer una URL válida para continuar.[/bold red]"
        )
        raise typer.Exit()

    quality_input = Prompt.ask(
        "\n[bold cyan]2. Calidad de video[/bold cyan] (max, 1080p, 720p, 480p, 360p, min)",
        default="max",
    )

    threads = IntPrompt.ask(
        "\n[bold cyan]3. Hilos de descarga simultánea[/bold cyan] (1-16)",
        default=10,
    )

    headless = Confirm.ask(
        "\n[bold cyan]4. ¿Ejecutar el navegador de fondo (modo oculto)?[/bold cyan]\n"
        "[dim]Escribe 'n' si la descarga te da error por medidas de seguridad de Cloudflare[/dim]",
        default=False,
    )

    override = Confirm.ask(
        "\n[bold cyan]5. ¿Sobreescribir archivos locales si ya existen?[/bold cyan]",
        default=False,
    )

    try:
        quality_enum = Quality(quality_input.lower())
    except ValueError:
        quality_enum = Quality.MAX
        console.print(
            f"\n[yellow]⚠️ Calidad '{quality_input}' no es válida. Usando calidad 'max' por defecto.[/yellow]"
        )

    console.print(
        f"\n🚀 [bold green]Iniciando descarga automatizada de:[/bold green] {url}\n"
    )

    asyncio.run(
        _download(
            url=url,
            quality=quality_enum,
            override=override,
            threads=threads,
            headless=headless,
        )
    )


async def _login():
    async with AsyncFacilito() as client:
        await client.login()


async def _logout():
    async with AsyncFacilito() as client:
        await client.logout()


async def _download(url: str, headless: bool = True, **kwargs):
    async with AsyncFacilito(headless=headless) as client:
        await client.download(url, **kwargs)


async def _set_cookies(path: Path):
    async with AsyncFacilito() as client:
        await client.set_cookies(path)
