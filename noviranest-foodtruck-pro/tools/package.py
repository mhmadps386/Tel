"""Build the release: workbooks, PDFs, previews, customer package folder and zip.

python tools/package.py
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import build_workbook as BW  # noqa: E402

V = BW.VERSION
NAME = f"NoviraNest_FoodTruck_Profit_Pricing_PRO_v{V}"
REL = ROOT / "release"
PKG = REL / NAME
RENDER = REL / "_render"
if REL.exists():
    shutil.rmtree(REL)
for d in ("01_Excel", "02_Google_Sheets", "03_Guides"):
    (PKG / d).mkdir(parents=True)

BW.build("template", PKG / "01_Excel" / f"NoviraNest_FoodTruck_PRO_TEMPLATE_v{V}.xlsx")
BW.build("sample", PKG / "01_Excel" / f"NoviraNest_FoodTruck_PRO_SAMPLE_v{V}.xlsx")

py = sys.executable
subprocess.run([py, str(ROOT / "tools/render.py"), "sample", str(RENDER), "--dpi", "400", "--crop"], check=True)
subprocess.run([py, str(ROOT / "tools/render.py"), "sample", str(RENDER), "--dpi", "400", "--crop", "--gbp"], check=True)
subprocess.run([py, str(ROOT / "tools/make_docs.py"), str(RENDER), str(PKG / "03_Guides")], check=True)
subprocess.run([py, str(ROOT / "tools/make_previews.py"), str(RENDER), str(ROOT / "listing/preview_images")], check=True)

shutil.copy(ROOT / "package_files/README_FIRST.txt", PKG)
shutil.copy(ROOT / "package_files/LICENSE.txt", PKG)
shutil.copy(ROOT / "package_files/HOW_TO_OPEN_IN_GOOGLE_SHEETS.txt", PKG / "02_Google_Sheets")
(PKG / "VERSION.txt").write_text(
    f"Food Truck Profit & Pricing System PRO\nVersion {V}\nRelease date {BW.RELEASE_DATE}\n\n"
    "Changelog\n- 1.0.0  First release.\n")
shutil.rmtree(RENDER)

z = REL / f"{NAME}.zip"
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(PKG.rglob("*")):
        if f.is_file():
            zf.write(f, f.relative_to(REL))
print("package:", z, round(z.stat().st_size / 1e6, 2), "MB")
for f in sorted(PKG.rglob("*")):
    if f.is_file():
        print(f"  {f.relative_to(REL)}  {f.stat().st_size / 1e3:.0f} KB")
