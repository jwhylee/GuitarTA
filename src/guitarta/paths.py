from pathlib import Path


APP_NAME = "GuitarTA"


def app_support_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / APP_NAME


def media_dir() -> Path:
    path = app_support_dir() / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_dir() -> Path:
    path = app_support_dir() / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    app_support_dir().mkdir(parents=True, exist_ok=True)
    return app_support_dir() / "guitarta.db"
