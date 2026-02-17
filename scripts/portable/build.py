#!/usr/bin/env python3
"""Build portable desktop application for current platform."""

from __future__ import annotations

import subprocess
import sys
import platform
import shutil
from pathlib import Path


def get_project_root() -> Path:
    return Path(__file__).parent.parent.parent


def build_windows():
    project_root = get_project_root()
    spec_file = project_root / "scripts" / "portable" / "rtv-desktop.spec"
    
    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}")
        sys.exit(1)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]
    
    print(f"Building Windows executable...")
    print(f"Command: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(project_root), check=True)
    
    dist_dir = project_root / "dist"
    exe_path = dist_dir / "RealTV.exe"
    
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"Windows executable created: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
    else:
        print(f"Warning: Expected output not found at {exe_path}")


def build_macos():
    project_root = get_project_root()
    spec_file = project_root / "scripts" / "portable" / "rtv-desktop.spec"
    
    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}")
        sys.exit(1)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]
    
    print(f"Building macOS application...")
    print(f"Command: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(project_root), check=True)
    
    dist_dir = project_root / "dist"
    app_path = dist_dir / "RealTV.app"
    
    if app_path.exists():
        print(f"macOS app created: {app_path}")
    else:
        print(f"Warning: Expected output not found at {app_path}")


def build_linux():
    project_root = get_project_root()
    spec_file = project_root / "scripts" / "portable" / "rtv-desktop.spec"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file),
    ]
    
    print(f"Building Linux binary...")
    subprocess.run(cmd, cwd=str(project_root), check=True)
    
    dist_dir = project_root / "dist"
    bin_path = dist_dir / "RealTV"
    
    if bin_path.exists():
        size_mb = bin_path.stat().st_size / (1024 * 1024)
        print(f"Linux binary created: {bin_path}")
        print(f"Size: {size_mb:.1f} MB")
    else:
        print(f"Warning: Expected output not found at {bin_path}")


def main():
    system = platform.system()
    
    print(f"Building RealTV Desktop for {system}...")
    print(f"Python: {sys.version}")
    print()
    
    try:
        import PyInstaller
    except ImportError:
        print("Error: PyInstaller not installed.")
        print("Install with: pip install pyinstaller")
        sys.exit(1)
    
    if system == "Windows":
        build_windows()
    elif system == "Darwin":
        build_macos()
    elif system == "Linux":
        build_linux()
    else:
        print(f"Unsupported platform: {system}")
        sys.exit(1)


if __name__ == "__main__":
    main()
