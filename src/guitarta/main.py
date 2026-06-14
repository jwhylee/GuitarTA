import flet as ft

from guitarta.ui.app import GuitarTAApp


def _preserve_packaged_runtime_dependencies() -> None:
    # Flet's packager can prune transitive networking dependencies that yt-dlp
    # imports lazily at runtime. Import them here so packaged desktop builds
    # keep the complete downloader stack.
    import certifi  # noqa: F401
    import charset_normalizer  # noqa: F401
    import idna  # noqa: F401
    import requests  # noqa: F401
    import urllib3  # noqa: F401


def main() -> None:
    _preserve_packaged_runtime_dependencies()
    ft.app(target=lambda page: GuitarTAApp(page).build())


if __name__ == "__main__":
    main()
