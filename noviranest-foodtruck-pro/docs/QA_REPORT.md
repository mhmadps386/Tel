# QA Report — Food Truck Profit & Pricing System PRO v1.0.0

Date: 2026-10-26

## 1. Automated tests — 102 / 102 passed

`python tests/run_qa.py` builds both workbooks, recalculates them in LibreOffice (headless), and compares cell values with
`tests/oracle.py` — an independent Python re-implementation of every calculation from the raw sample data — and with
hand-calculated cases. Full list: `tests/QA_RESULTS.md`.

| Area | What was verified |
|---|---|
| Sample workbook | 0 formula errors in ~34,000 formulas |
| Menu pricing | 13 items × ingredient cost, total cost, suggested price, profit, margin, markup, food cost %, status; margin ≠ markup identity; LOSS recommendation text |
| Unit conversion | All 53 recipe lines (oz→lb, ml→l, tbsp→l, fl oz→gal, g→kg, cup→gal) |
| Monthly report | 12 months × 12 columns (revenue, items, COGS, waste, fixed/labour/event/variable opex, net, stock purchases); P&L identities; exclusions (stock purchases, owner's draw); labour not in COGS |
| Dashboard | KPI cards, top-5 rankings by units and by gross profit, break-even progress, alert counts, sample-data banner |
| Inventory & waste | 32 ingredients × usage from sales, waste, on hand, value, status; total value; waste values |
| Break-even | 12 outputs incl. contribution, BE items/day/revenue, target profit, margin of safety |
| Event predictor | 3 scenarios × 6 outputs; actuals pulled from Sales Log by event name; variance |
| Scenario simulator | All 8 presets + custom levers; price-needed; source data untouched |
| Period switching | July view; empty December (no errors, $0, empty-state messages) |
| Currency | GBP symbols in cards/headers/recommendations, identical amounts (no FX conversion); invalid currency falls back safely |
| Template | 0 errors when empty; empty-state guidance on Dashboard, Break-Even, Event, Simulator; no leftover sample rows |
| Invalid input | Text dates, negative/zero qty, unknown items, missing prices, price overrides, other-year sales, unknown categories, non-numeric amounts, refunds, unit mismatches (recipe & waste), negative stock, zero contribution, ≥100 % variable cost — each flagged and excluded, totals hand-checked (e.g. net −41) |
| High volume | 3,000 sales + 1,500 expenses + 50 items: 0 errors, monthly revenue/COGS/opex exact |
| Structure | Every calculated column uses one consistent formula on every row; all named ranges defined; no volatile/unsupported functions; no VBA |
| Excel strictness | No `=` in validation formulas; no number-format ID clashes; no overlapping merges; formulas < 8,192 chars; only Excel-2010-era functions |

## 2. Google Sheets

25 formula patterns evaluated by Google Sheets itself via a probe file in the owner's Drive: identical to LibreOffice
(see `tests/gsheets/RESULTS.md`). The full .xlsx could not be uploaded from the build environment — see section 5.

## 3. Visual inspection

Every worksheet (sample + template, USD + GBP) was rendered to PNG through LibreOffice and inspected, as were all 11
preview images and the 3 PDFs. Issues found and fixed during inspection:

- Navigation links unreadable on the dark Dashboard header → moved to a light row.
- `$` disappearing where two conditional rules overlapped (LibreOffice applies only the first) → negative numbers now
  use native `[Red]` formats instead of a second rule.
- Truncated labels on the Monthly Report summary; Break-Even chart covering its own data; 16-category expense chart
  dropping labels → replaced by a 7-bar "where the money goes" chart with value labels.
- Chart legends showing line-broken header text; month labels wrapping.
- Number inputs left-aligned; status columns not centred; brand label clipped on narrow sheets.
- Preview images: hero subtitle running under the screenshot; menu-pricing screenshot too small; "13 worksheets" (actually 14).
- PDFs: nearly blank page 2; wrong section cross-reference; a glyph (⌈) missing from the font.

## 4. Bugs found by testing and fixed

| Bug | Impact | Fix |
|---|---|---|
| Hidden ranking column `AA` never received formulas | "Most profitable items" table empty | Column list handling fixed; test added |
| `COUNTIFS(r,"<>OK",r,"<>")` counts formula blanks as non-empty (inconsistent across apps) | Alerts showed 1,258 "bad" expense rows | Replaced by `SUMPRODUCT((r<>"")*(r<>"OK"))` (verified in Google Sheets) |
| Payroll dated the Monday after the week | October showed a loss with no sales | Sample expenses booked on the last trading day of the week |
| Validation formulas written with a leading `=` | Excel would likely flag the file for repair and drop dropdowns | Stripped; strictness test added |

## 5. Remaining limitations (honest list)

1. **Not opened in Microsoft Excel.** Excel is not available in the build environment. Compatibility rests on: Excel-2007/2010
   functions only, OOXML strictness checks, and LibreOffice recalculation. → Run `docs/MANUAL_TEST_CHECKLIST.md` section A.
2. **Full workbook not opened in Google Sheets.** Formula semantics verified by probe; conversion of charts, dropdowns,
   conditional formats, protection and links must be checked manually (checklist section B).
3. **Currency symbol on money cells in Google Sheets** — not possible with conditional formatting there; symbols shown in
   headers and cards instead (disclosed to customers).
4. **No cached values in the .xlsx.** Values appear after Excel calculates on opening; in Excel's *Protected View* cells may look
   empty until *Enable Editing* (customers are told to click it).
5. **Standard costing.** COGS for past months uses current recipe costs.
6. One reporting year per file; no tax/VAT; theoretical inventory usage.
7. Preview images are LibreOffice renders, so fonts/colours are close to, not identical with, Excel/Sheets.
