"""Mutable data location, independent of the installed application resources."""
import os
import sys
from pathlib import Path


def data_directory(*, packaged=None, platform=None, environ=None, home=None) -> Path:
    env = os.environ if environ is None else environ
    if env.get("COLLOQUILY_DATA_DIR"):
        return Path(env["COLLOQUILY_DATA_DIR"]).expanduser().resolve()
    packaged = getattr(sys, "frozen", False) if packaged is None else packaged
    if not packaged:
        return Path(__file__).resolve().parent / "data"
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Colloquily"
    if platform == "win32":
        return Path(env.get("APPDATA", home / "AppData" / "Roaming")) / "Colloquily"
    return Path(env.get("XDG_DATA_HOME", home / ".local" / "share")) / "Colloquily"
