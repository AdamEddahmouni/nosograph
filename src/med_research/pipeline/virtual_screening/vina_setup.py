"""
AutoDock Vina Binary Download Helper

Downloads the pre-compiled AutoDock Vina binary for the current platform
from the official GitHub releases. Handles Windows, macOS, and Linux.

Usage:
    python virtual_screening/vina_setup.py          # Interactive
    python virtual_screening/vina_setup.py --auto   # Non-interactive
    python virtual_screening/vina_setup.py --check  # Check status only
"""

import argparse
import os
import platform
import shutil
import sys
import urllib.request
from pathlib import Path

VINA_VERSION = "1.2.5"
VINA_DOWNLOADS = {
    "win32": {
        "url": f"https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v{VINA_VERSION}/vina_{VINA_VERSION}_win64.exe",
        "filename": "vina.exe",
    },
    "cygwin": {
        "url": f"https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v{VINA_VERSION}/vina_{VINA_VERSION}_win64.exe",
        "filename": "vina.exe",
    },
    "darwin": {
        "url": f"https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v{VINA_VERSION}/vina_{VINA_VERSION}_mac_12_64",
        "filename": "vina",
    },
    "linux": {
        "url": f"https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v{VINA_VERSION}/vina_{VINA_VERSION}_linux_x86_64",
        "filename": "vina",
    },
}

BIN_DIR = Path(__file__).parent / "bin"


def _system() -> str:
    sysname = sys.platform
    if sysname.startswith("win") or sysname == "cygwin":
        return "win32"
    elif sysname == "darwin":
        return "darwin"
    else:
        return "linux"


def check_vina() -> str | None:
    """Check if Vina binary is available on PATH or in project bin/."""
    candidates = ["vina", "vina.exe"]
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path

    for name in candidates:
        candidate = BIN_DIR / name
        if candidate.is_file():
            return str(candidate)

    return None


def download_vina(auto: bool = False) -> str | None:
    """Download and install the AutoDock Vina binary.

    Args:
        auto: If True, skip confirmation prompts.

    Returns:
        Path to installed Vina binary, or None on failure.
    """
    sys_name = _system()
    if sys_name not in VINA_DOWNLOADS:
        print(f"❌ Unsupported platform: {sys.platform}")
        return None

    info = VINA_DOWNLOADS[sys_name]
    dest = BIN_DIR / info["filename"]

    if dest.is_file():
        print(f"✅ Vina binary already installed: {dest}")
        return str(dest)

    print(f"\n🔽 AutoDock Vina v{VINA_VERSION}")
    print(f"   Platform: {platform.system()} ({platform.machine()})")
    print(f"   Install to: {dest}")
    print(f"   Download: {info['url']}")

    if not auto:
        answer = input("\nDownload and install? (y/n): ").strip().lower()
        if answer not in ("y", "yes"):
            print("   Skipped.")
            return None

    BIN_DIR.mkdir(parents=True, exist_ok=True)

    try:
        print("   Downloading...")
        req = urllib.request.Request(info["url"], headers={"User-Agent": "LupusPlatform/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"   ❌ Download failed: {e}")
        print(f"   ➜ Please download manually from: {info['url']}")
        print(f"   ➜ Save as: {dest}")
        return None

    dest.write_bytes(data)

    if sys.platform != "win32":
        os.chmod(dest, 0o755)

    if dest.is_file():
        print(f"   ✅ Installed: {dest}")
        return str(dest)
    else:
        print("   ❌ Installation failed.")
        return None


def print_status():
    """Print current Vina availability status."""
    vina_path = check_vina()
    bin_dir_exists = BIN_DIR.is_dir()
    bin_contents = list(BIN_DIR.glob("vina*")) if bin_dir_exists else []

    print("\nAutoDock Vina Status:")
    print(f"   In PATH:           {'✅ ' + vina_path if vina_path else '❌ not found'}")
    print(f"   Project bin/:      {'✅ ' + ', '.join(str(p.name) for p in bin_contents) if bin_contents else 'empty'}")
    print(f"   Platform:          {platform.system()} {platform.machine()}")

    if not vina_path:
        print("\n   To install: python virtual_screening/vina_setup.py --auto")
        print("   Manual: download from https://github.com/ccsb-scripps/AutoDock-Vina/releases")
        print(f"            save to {BIN_DIR / 'vina'} (or vina.exe on Windows)")


def main():
    parser = argparse.ArgumentParser(
        description="AutoDock Vina binary download helper for the Lupus Research Platform"
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Non-interactive: download and install without prompting",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Check current Vina installation status only",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-download even if already installed",
    )
    args = parser.parse_args()

    if args.check:
        print_status()
        return

    if args.force:
        vina_path = check_vina()
        if vina_path:
            if vina_path.startswith(str(BIN_DIR)):
                Path(vina_path).unlink(missing_ok=True)
            else:
                print(f"⚠️  Vina found at {vina_path} (outside project). Force only removes project-binary.")
        else:
            print("⚠️  No Vina binary found to remove.")

    existing = check_vina()
    if existing and not args.force:
        print(f"✅ Vina is already available: {existing}")
        print_status()
        return

    result = download_vina(auto=args.auto)
    if result:
        print(f"\n✅ Setup complete. Vina binary: {result}")
    else:
        print("\n⚠️  Vina binary not installed. Use --check for status.")


if __name__ == "__main__":
    main()
