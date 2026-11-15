"""
export.py - Exports the designs and the design-process sheets using headless
Google Chrome.

  designs/*.png  high-resolution images (A3 posters at 2x: 2246 x 3174 px)
  designs/*.pdf  print-ready A3 PDFs of the two posters
  process/*.png  colour, typography, layout and mockup sheets

Usage (from the project root, after build.py):
    python tools/export.py

Needs Google Chrome or Chromium. Set CHROME=/path/to/chrome if it is not
found automatically.
"""

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DESIGNS = ROOT / "designs"
PROCESS = ROOT / "process"

A3 = (1123, 1587)  # 297 x 420 mm in CSS pixels

# (source html, output name, width, height, pixel scale, also make a PDF)
DESIGN_EXPORTS = [
    (SITE / "results.html", "01-results", *A3, 2, True),
    (SITE / "councillors.html", "02-councillors", *A3, 2, True),
    (SITE / "square.html", "03-square", 1080, 1080, 1, False),
]

# Process sheets come after the designs: the mockups use the design images.
SHEETS = [
    (PROCESS / "src" / f"{name}.html", PROCESS / f"{name}.png", 1600, 1000)
    for name in ("palette", "typography", "layout", "mockups")
]


def find_chrome():
    for name in (os.environ.get("CHROME"), "google-chrome", "chromium", "chromium-browser", "chrome"):
        if name and shutil.which(name):
            return shutil.which(name)
    raise SystemExit("Chrome not found. Install it or set CHROME=/path/to/chrome")


def chrome(*args):
    subprocess.run(
        [find_chrome(), "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
         "--virtual-time-budget=6000", *args],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def png(source, out, width, height, scale=1):
    chrome(f"--window-size={width},{height}", f"--force-device-scale-factor={scale}",
           f"--screenshot={out}", source.as_uri())
    print(f"Exported {out.relative_to(ROOT)}")


def pdf(source, out):
    chrome("--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={out}", source.as_uri())
    print(f"Exported {out.relative_to(ROOT)}")


def main():
    DESIGNS.mkdir(exist_ok=True)
    for source, name, width, height, scale, make_pdf in DESIGN_EXPORTS:
        png(source, DESIGNS / f"{name}.png", width, height, scale)
        if make_pdf:
            pdf(source, DESIGNS / f"{name}-A3-print.pdf")
    for source, out, width, height in SHEETS:
        png(source, out, width, height)


if __name__ == "__main__":
    main()
