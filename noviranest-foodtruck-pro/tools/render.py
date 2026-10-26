"""Render every worksheet to PNG via LibreOffice (real recalculated values) for visual QA and previews.

python tools/render.py sample|template OUTDIR [--gbp]
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import build_workbook as BW  # noqa: E402

kind, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
x = out / f"preview_{kind}.xlsx"
BW.build(kind, x, preview=True)
if "--gbp" in sys.argv:
    from openpyxl import load_workbook
    raise SystemExit("--gbp not supported (openpyxl would drop charts)")
subprocess.run([sys.executable, str(ROOT / "tools/lo/recalc.py"), str(x), "300"], check=True, capture_output=True)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(out), str(x)], check=True, capture_output=True)
pdf = out / f"preview_{kind}.pdf"
subprocess.run(["pdftoppm", "-r", "110", "-png", str(pdf), str(out / f"{kind}")], check=True)
names = [ws for ws in BW.PREVIEW_AREAS]
pngs = sorted(out.glob(f"{kind}-*.png"))
for p, n in zip(pngs, names):
    p.rename(out / f"{kind}_{names.index(n):02d}_{n.replace(' ', '_')}.png")
print(len(pngs), "pages")
