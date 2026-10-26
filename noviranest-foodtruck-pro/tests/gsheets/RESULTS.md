# Google Sheets compatibility probe — results (2026-10-26)

**Method.** `make_probe.py` writes `probe.csv` containing the 25 riskiest formula patterns the workbook uses
(SUMIFS with date ranges, SUMPRODUCT blank-safe counts, N() on blanks, INDEX/MATCH, IFERROR, LARGE tie-break
ranking, CEILING, TEXT money/month/percent formats, REPT bars, COUNTIF(S), AVERAGEIF, ROUNDUP, SEARCH, date serials,
unit conversion). The CSV was uploaded to Google Drive and **converted and calculated by Google Sheets**
("NoviraNest QA probe - formula compatibility", owner's Drive, safe to delete). The same file was calculated
by LibreOffice. Results were read back and compared.

| Test | Google Sheets | LibreOffice | Match |
|---|---|---|---|
| T01 SUMIFS date range + status | 125 | 125 | ✅ |
| T02 SUMPRODUCT((r<>"")*(r<>"OK")) | 2 | 2 | ✅ |
| T03 N() on blank/text | 5 | 5 | ✅ |
| T04 INDEX/MATCH | Soda | Soda | ✅ |
| T05 IFERROR(INDEX/MATCH&"") missing | ? | ? | ✅ |
| T06 LARGE + ROW() tie-break key | Burger | Burger | ✅ |
| T07 CEILING(x,0.25) | 9.25 | 9.25 | ✅ |
| T08 TEXT(190589.5,"#,##0") | $190,590 | $190,590 | ✅ (half-up, same as Excel) |
| T09 TEXT(date,"mmm") | يوليو (account locale = Arabic) | Jul | ✅ locale-dependent by design (Excel behaves the same) |
| T10 REPT progress bar | ██████░░░░ | ██████░░░░ | ✅ |
| T11 COUNTIF ">0" | 6 | 6 | ✅ |
| T12 ISNA(MATCH) | TRUE | TRUE | ✅ |
| T13 SUMIFS ignores text cells | 112 | 112 | ✅ |
| T14 SUMPRODUCT activity months | 1 | 1 | ✅ |
| T15 AVERAGEIF | 37.333 | 37.333 | ✅ |
| T16 ROUNDUP | 1573 | 1573 | ✅ |
| T17 IF(N(blank)<=0,…) | Set a price | Set a price | ✅ |
| T18 ISNUMBER(SEARCH) | TRUE | TRUE | ✅ |
| T19 COUNTIFS 3 criteria | 2 | 2 | ✅ |
| T20 DATE serial difference | 9556 | 9556 | ✅ |
| T21 TEXT(x,"0.0%") | 62.4% | 62.4% | ✅ |
| T22 unit conversion via INDEX/MATCH | #VALUE! in CSV probe → 9.375 in probe 2 | 9.375 | ✅ see note |
| T23 SUMIFS item + date + status | 16 | 16 | ✅ |
| T24 negative money text | -£41 | -£41 | ✅ |
| T25 ROUND(2.675,2) | 2.68 | 2.68 | ✅ |

**T22 note.** The owner's Google account uses an Arabic locale (decimal separator "٫"), so Google's CSV importer
read the literal `28.349523125` as *text*. A second probe with the factor entered as a numeric expression returned
9.375, "Unit mismatch" and 1.30 exactly as expected. In the .xlsx product, factors are stored as numbers, so the
import cannot mis-read them. This is a CSV-import artefact, not a formula incompatibility.

## Not testable through this channel (must be checked manually in Google Sheets — see checklist)

The Drive connector available here accepts uploads only as inline text, so the full .xlsx (≈1 MB) could not be
uploaded from this environment. Features below are documented from Google's published import behaviour and must be
confirmed with `docs/MANUAL_TEST_CHECKLIST.md` before listing:

- Conditional-format **number formats** ($/£ on money cells) — Google Sheets does not support number formats in
  conditional formatting; money cells show plain numbers and the **headers/KPI cards carry the symbol**.
- Chart styling (colours, data labels) after conversion.
- Internal hyperlinks (navigation links) after conversion.
- Data-validation dropdowns that reference other sheets and named ranges.
- Sheet protection on the Dashboard.
