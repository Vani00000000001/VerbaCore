import os
import platform
from pathlib import Path


def get_project_root() -> Path:
    """Return root repository directory if running from source."""
    return Path(__file__).resolve().parent.parent.parent.parent


def get_data_dir() -> Path:
    """
    Return root application storage directory.
    Respects VERBACORE_DATA_DIR, falling back to OS standard application directories.
    """
    if env := os.environ.get("VERBACORE_DATA_DIR"):
        path = Path(env).resolve()
    else:
        system = platform.system()
        if system == "Windows":
            local_appdata = os.environ.get("LOCALAPPDATA")
            base = Path(local_appdata) if local_appdata else (Path.home() / "AppData" / "Local")
            path = base / "verbacore"
        elif system == "Darwin":
            path = Path.home() / "Library" / "Application Support" / "verbacore"
        else:
            xdg = os.environ.get("XDG_DATA_HOME")
            base = Path(xdg) if xdg else (Path.home() / ".local" / "share")
            path = base / "verbacore"

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_models_dir() -> Path:
    """Return model cache directory."""
    if env := os.environ.get("VERBACORE_MODELS_DIR"):
        p = Path(env).resolve()
    else:
        p = get_data_dir() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_uploads_dir() -> Path:
    p = get_data_dir() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_reports_dir() -> Path:
    p = get_data_dir() / "reports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_recordings_dir() -> Path:
    p = get_data_dir() / "recordings"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_font_search_paths() -> list[Path]:
    """Return font candidate paths in priority order across OS platforms."""
    candidates = []

    # Bundled font directory inside package
    bundled = Path(__file__).resolve().parent.parent / "resources" / "fonts"
    if bundled.is_dir():
        candidates.extend(bundled.glob("*.ttf"))
        candidates.extend(bundled.glob("*.ttc"))
        candidates.extend(bundled.glob("*.otf"))

    system = platform.system()
    if system == "Windows":
        win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidates.extend([
            win_fonts / "segoeui.ttf",
            win_fonts / "Nirmala.ttc",
            win_fonts / "arial.ttf",
            win_fonts / "calibri.ttf"
        ])
    elif system == "Darwin":
        candidates.extend([
            Path("/Library/Fonts/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
            Path("/Library/Fonts/NotoSans-Regular.ttf")
        ])
    else:
        candidates.extend([
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansTamil-Regular.otf")
        ])

    return [p for p in candidates if p.is_file()]
