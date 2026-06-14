from pathlib import Path
import sys

import flet as ft

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from guitarta.main import app

ft.app(target=app)
