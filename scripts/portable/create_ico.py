#!/usr/bin/env python3
"""Create Windows .ico file from logo.png."""

from __future__ import annotations

import sys
from pathlib import Path


def create_ico():
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed. Install with: pip install Pillow")
        print("Skipping .ico creation.")
        return False
    
    project_root = Path(__file__).parent.parent
    logo_png = project_root / "assets" / "logo.png"
    logo_ico = project_root / "assets" / "logo.ico"
    
    if not logo_png.exists():
        print(f"Error: logo.png not found at {logo_png}")
        return False
    
    print(f"Converting {logo_png} to {logo_ico}...")
    
    img = Image.open(logo_png)
    
    # Create multiple sizes for .ico (Windows standard sizes)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    icons = []
    for size in sizes:
        resized = img.resize(size, Image.Resampling.LANCZOS)
        icons.append(resized)
    
    # Save as .ico
    icons[0].save(
        logo_ico,
        format="ICO",
        sizes=[(i.width, i.height) for i in icons],
        append_images=icons[1:],
    )
    
    print(f"Created: {logo_ico}")
    return True


if __name__ == "__main__":
    success = create_ico()
    sys.exit(0 if success else 1)
