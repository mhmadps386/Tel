# NoviraNest — Food Truck Profit & Pricing System PRO (v1.0.0)

Digital product for Etsy / Gumroad: an Excel + Google Sheets financial toolkit for food trucks and small caterers.

## Deliverables

| Path | What |
|---|---|
| `release/NoviraNest_FoodTruck_Profit_Pricing_PRO_v1.0.0.zip` | **Customer download** (same content as the folder next to it) |
| `release/…/01_Excel/` | TEMPLATE and SAMPLE workbooks (.xlsx) |
| `release/…/02_Google_Sheets/` | How to use the workbook in Google Sheets |
| `release/…/03_Guides/` | Quick-Start Guide, Feature Overview, Customer FAQ (PDF) |
| `listing/preview_images/` | 9 Etsy images (3000×2250) + Gumroad cover (1280×720) and thumbnail (600×600) |
| `listing/LISTING_COPY.md` | Draft title, description, 13 tags, pricing & positioning — **not published** |
| `docs/01_competitor_research.md` | Competitor research and differentiators |
| `docs/02_architecture_and_calc_spec.md` | Sheet architecture and calculation specification |
| `docs/QA_REPORT.md` | QA summary, bugs fixed, limitations |
| `docs/MANUAL_TEST_CHECKLIST.md` | 25-minute Excel + Google Sheets check to do before publishing |
| `tests/QA_RESULTS.md` | Latest automated test results (102 checks) |

## Rebuild

```bash
pip install openpyxl reportlab pillow matplotlib   # LibreOffice + poppler-utils required
python tools/otf2ttf.py          # once: Inter fonts for the PDFs
python tools/package.py          # workbooks, renders, PDFs, previews, zip
python tests/run_qa.py           # automated QA (≈3 min)
```

Source: `src/build_workbook.py` (workbook), `src/theme.py` (visual identity), `src/sample_data.py` (fictional demo data).
