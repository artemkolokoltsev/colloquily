"""Build on the destination OS/architecture: PyInstaller does not cross-compile."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(root / "build/pyinstaller-config"))
host = subprocess.check_output(["rustc", "--print", "host-tuple"], text=True).strip()
allowed = {"aarch64-apple-darwin", "x86_64-apple-darwin", "x86_64-pc-windows-msvc"}
if host not in allowed:
    raise SystemExit(f"Desktop build target not configured: {host}")
python_arm = platform.machine().lower() in {"arm64", "aarch64"}
if python_arm != host.startswith("aarch64"):
    raise SystemExit("Python architecture must match the Rust host target. Use native Python and Rust.")
command = [sys.executable, "-m", "PyInstaller", "--noconfirm",
    "--distpath", str(root / "build/sidecar"), "--workpath", str(root / "build/pyinstaller"),
    str(root / "scripts/colloquily-backend.spec")]
subprocess.run(command, cwd=root, check=True)
ext = ".exe" if sys.platform == "win32" else ""
source = root / f"build/sidecar/colloquily-backend{ext}"
destination = root / f"src-tauri/binaries/colloquily-backend-{host}{ext}"
destination.parent.mkdir(parents=True, exist_ok=True)
# Verify the frozen runtime before making it available to the desktop bundle.
subprocess.run([str(source), "--self-test"], check=True, timeout=180)
shutil.copy2(source, destination)
print(f"Built {destination}")
