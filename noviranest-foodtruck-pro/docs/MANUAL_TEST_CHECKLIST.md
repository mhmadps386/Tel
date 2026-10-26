# Manual pre-launch checklist (≈ 25 minutes) — required before publishing

Automated QA ran in LibreOffice and a Google Sheets formula probe (see `tests/QA_RESULTS.md`,
`tests/gsheets/RESULTS.md`). Microsoft Excel itself is not available in the build environment, and the full .xlsx
could not be uploaded to Google Sheets from it. These checks close that gap. Tick each one.

## A. Microsoft Excel (Windows or Mac, Microsoft 365 or 2016+; ideally also one older version)

Open `release/…/01_Excel/NoviraNest_FoodTruck_PRO_SAMPLE_v1.0.0.xlsx`.

- [ ] Opens with **no** "We found a problem with some content… repair?" message.
- [ ] After *Enable Editing*, the Dashboard shows Total revenue **$190,589**, Gross profit **$143,456**, Net profit **$30,216**, Net margin **15.9%** (the values the automated tests verified).
- [ ] Money cells show **$** (e.g. Menu Pricing › Your menu price "$11.00").
- [ ] Settings › Currency → **GBP**: money cells, headers and cards switch to **£**; numbers unchanged. Switch back to USD.
- [ ] Settings › Dashboard period → **July**: cards change (Revenue $36,153). Back to Full Year.
- [ ] Both Dashboard charts display; the bar chart shows value labels.
- [ ] Click "› Menu Pricing" on the Dashboard: it jumps to that sheet.
- [ ] Sales Log: dropdowns in Menu item / Payment method; typing "abc" in Qty is rejected with a message.
- [ ] Recipe Builder: change a unit on any row to `each` where the stock unit is `kg` → "Unit mismatch" in red. Undo.
- [ ] Scenario Simulator: change the preset → Impact table changes; Monthly Report unchanged.
- [ ] Dashboard is protected (typing is refused) and *Review › Unprotect Sheet* works with no password.
- [ ] Open the TEMPLATE file: no errors (#DIV/0!, #VALUE!), Dashboard shows $0 and the "No sales recorded" banner.

## B. Google Sheets

Upload the SAMPLE .xlsx to Google Drive → open → *File › Save as Google Sheets*.

- [ ] Conversion completes without an error banner.
- [ ] Dashboard cards show the same values as in A (formatting may use plain numbers).
- [ ] Headers show "($)"; Settings › Currency → GBP changes headers and Dashboard cards to £.
- [ ] Dropdowns work on Sales Log (Menu item), Expenses (Category), Recipe Builder (Unit), Settings (Currency, Period).
- [ ] Status colours (green OK / red LOSS / amber Reorder) appear.
- [ ] Charts appear on the Dashboard, Break-Even and Scenario Simulator (styling may differ).
- [ ] Navigation links: note whether they jump. If not, the guide already tells customers to use the tabs.
- [ ] Add a new sale row (today, Smash Burger, qty 1): Dashboard revenue increases by 11.
- [ ] Share › "Anyone with the link: Viewer" and create a `/copy` link **only if** you want to offer a Google Sheets copy link in the listing (optional; keep the original private).

## C. Package

- [ ] Unzip the release zip on a clean computer; all files open; PDFs readable on a phone.
- [ ] Etsy listing preview: images crisp, text readable on mobile.

Record anything that fails and send it to me — I'll fix and re-run the automated suite.
