"""Render every worksheet to PNG via LibreOffice (real recalculated values) for visual QA and previews.

python tools/render.py sample|template OUTDIR [--dpi 110] [--gbp]
"""
import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import build_workbook as BW  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("kind")
ap.add_argument("out")
ap.add_argument("--dpi", type=int, default=110)
ap.add_argument("--gbp", action="store_true")
ap.add_argument("--crop", action="store_true")
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
tag = a.kind + ("_gbp" if a.gbp else "")
x = out / f"preview_{tag}.xlsx"
BW.build(a.kind, x, preview=True, currency="GBP" if a.gbp else "USD")
subprocess.run([sys.executable, str(ROOT / "tools/lo/recalc.py"), str(x), "300"], check=True, capture_output=True)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out), str(x)], check=True, capture_output=True)
subprocess.run(["pdftoppm", "-r", str(a.dpi), "-png", str(out / f"preview_{tag}.pdf"), str(out / tag)], check=True)
names = list(BW.PREVIEW_AREAS)
for i, p in enumerate(sorted(out.glob(f"{tag}-*.png"))):
    dst = out / f"{tag}_{i:02d}_{names[i].replace(' ', '_')}.png"
    p.rename(dst)
    if a.crop:
        im = Image.open(dst).convert("RGB")
        bbox = ImageChops.difference(im, Image.new("RGB", im.size, "white")).getbbox()
        if bbox:
            im.crop(bbox).save(dst)
print("rendered", tag)
