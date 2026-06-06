import flet as ft

from guitarta.ui.app import GuitarTAApp


def main() -> None:
    ft.app(target=lambda page: GuitarTAApp(page).build())


if __name__ == "__main__":
    main()
