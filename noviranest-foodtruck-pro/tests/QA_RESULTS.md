# Automated QA results

Run: 2026-10-26 17:57 · engine: LibreOffice headless recalculation · expected values: tests/oracle.py (independent) and hand calculations

**102 / 102 checks passed**

## Formula consistency & references

| Result | Check |
|---|---|
| PASS | Every calculated column uses one consistent formula on every row |
| PASS | All named ranges used in formulas are defined |
| PASS | No volatile/unsupported functions (INDIRECT, OFFSET, XLOOKUP, FILTER, LET, LAMBDA, macros) |
| PASS | File is .xlsx (no VBA project) |

## Excel strictness (OOXML)

| Result | Check |
|---|---|
| PASS | sample: data-validation formulas have no leading '=' |
| PASS | sample: no number-format ID collisions |
| PASS | template: data-validation formulas have no leading '=' |
| PASS | template: no number-format ID collisions |
| PASS | No overlapping merged ranges |
| PASS | All formulas under Excel's 8,192-character limit |
| PASS | Only Excel-2010-era functions used (no _xlfn / dynamic arrays) |

## Sample workbook

| Result | Check |
|---|---|
| PASS | LibreOffice recalculation: zero formula errors |
| PASS | Formula count above 30,000 (logs fully pre-formulated) |

## Menu pricing

| Result | Check |
|---|---|
| PASS | Ingredient cost, total cost, suggested price, profit, margin, markup, food cost %, status (13 items) |
| PASS | Loss-making item flagged LOSS |
| PASS | Margin and markup are mathematically distinct (markup = margin/(1-margin)) |
| PASS | Recommendation text for LOSS item quotes suggested price |

## Recipe Builder / unit conversion

| Result | Check |
|---|---|
| PASS | All 55 recipe lines convert and cost correctly (oz->lb, ml->l, tbsp->l, fl oz->gal, g->kg, cup->gal) |

## Monthly report

| Result | Check |
|---|---|
| PASS | 12 months x 12 columns match oracle (revenue, items, COGS, waste, opex by type, net, stock, ingredient) |
| PASS | Annual total net profit = oracle |
| PASS | Net profit identity: GP - waste - opex |
| PASS | Stock purchases and owner's draw excluded from opex |
| PASS | Labour appears only in opex (COGS = ingredients+packaging+other, no labour) |

## Dashboard (Full Year)

| Result | Check |
|---|---|
| PASS | Revenue card |
| PASS | Gross profit card |
| PASS | Net profit card |
| PASS | Net margin card |
| PASS | Top-5 best sellers ranking |
| PASS | Top-5 most profitable ranking |
| PASS | Top-5 GP values |
| PASS | Break-even progress = revenue / (BE revenue x 12) |
| PASS | Alert counts: 1 LOSS, 1 below target, reorders match oracle, 0 bad rows |
| PASS | Sample-data disclaimer banner shown |

## Inventory & waste

| Result | Check |
|---|---|
| PASS | 32 ingredients: usage from sales, waste, on-hand, value, status |
| PASS | Total stock value |
| PASS | Waste log values (unit-converted) |

## Break-even

| Result | Check |
|---|---|
| PASS | Contribution, ratio, BE items/day/revenue, target-profit items/revenue, margin of safety |
| PASS | Break-even check: revenue at BE items covers fixed costs |

## Event predictor

| Result | Check |
|---|---|
| PASS | Worst/base/best customers, orders, revenue, profit, break-even orders & attendance |
| PASS | Actual revenue/items/COGS pulled from Sales Log by event name |
| PASS | Actual profit and variance vs base |
| PASS | Verdict text present |

## Scenario simulator

| Result | Check |
|---|---|
| PASS | Baseline net profit / month |
| PASS | Scenario net profit (ingredient +10%) |
| PASS | Price needed to keep baseline profit |
| PASS | Baseline x 9 months of data = annual net (excluding Oct-Dec) |

## Period switching

| Result | Check |
|---|---|
| PASS | Dashboard period = July: revenue / net cards |
| PASS | July best sellers re-rank |
| PASS | Break-even progress uses 1 month for a month period |
| PASS | Empty month (December): no errors, $0 cards, empty-state message |

## Scenario switching

| Result | Check |
|---|---|
| PASS | Preset 'Ingredient inflation +10%' net profit |
| PASS | Preset 'Menu price increase +5%' net profit |
| PASS | Preset 'Price +5%, volume -3%' net profit |
| PASS | Preset 'Busy season (+25% volume)' net profit |
| PASS | Preset 'Slow season (-30% volume)' net profit |
| PASS | Preset 'Wage increase +8%' net profit |
| PASS | Preset 'Event fees +20%' net profit |
| PASS | Preset 'Perfect storm' net profit |
| PASS | Custom levers net profit & price needed |
| PASS | Scenario does not modify source data (Monthly Report unchanged) |

## Currency

| Result | Check |
|---|---|
| PASS | GBP: KPI shows £ with identical amount (no FX conversion) |
| PASS | GBP: headers switch symbol |
| PASS | GBP: values unchanged vs USD |
| PASS | GBP: recommendation text uses £ |
| PASS | Invalid currency typed (EUR) falls back to USD without errors |

## Template (empty)

| Result | Check |
|---|---|
| PASS | Zero formula errors when completely empty |
| PASS | KPI cards show $0 / '-' (no #DIV/0!) |
| PASS | Empty-state guidance on Dashboard |
| PASS | Break-even status asks for fixed costs |
| PASS | Event verdict asks for inputs |
| PASS | Simulator explains missing baseline |
| PASS | No error strings anywhere |
| PASS | No sample rows left in logs |

## Edge cases & invalid input

| Result | Check |
|---|---|
| PASS | Zero spreadsheet errors with invalid inputs |
| PASS | Recipe g -> kg converts (150 g beef at 10/kg = 1.50) |
| PASS | Unit mismatch (g vs each) flagged and NOT costed |
| PASS | Ingredient with no price flagged |
| PASS | Recipe for item not on menu flagged |
| PASS | Negative recipe quantity rejected |
| PASS | Menu: recipe cost sums only valid lines (1.50 + 0.50) |
| PASS | Menu: total cost, margin 65%, markup 185.7% (hand-calculated) |
| PASS | Menu: suggested price at 60% default target = 3.5/0.4 = 8.75 |
| PASS | Menu: zero price -> 'Set a price' (no divide by zero) |
| PASS | Menu: override ingredient cost used; price below cost -> LOSS |
| PASS | Duplicate ingredient name flagged via status/CF and lookup uses first |
| PASS | Sales checks: OK / bad date / qty<=0 / unknown item / no price / override / other year / missing item |
| PASS | Price override used (2 x 12 = 24) |
| PASS | Only valid 2026 sales counted in March (10x10 + 2x12 = 124) |
| PASS | Prior-year sale excluded from 2026 totals |
| PASS | Expense checks: unknown category and non-numeric flagged; refund OK |
| PASS | Opex: fixed 100-20 refund = 80, labour 50; draw & stock purchase excluded |
| PASS | Waste unit mismatch (kg for 'each' buns) flagged; 500 g beef = 5.00 |
| PASS | Net profit hand-calculated: 124 - 30 - 5 - 130 = -41 |
| PASS | Inventory: beef used = 12 burgers x 0.15 kg = 1.8; waste 0.5 kg |
| PASS | Inventory: on hand negative -> 'Recount (negative)', value floored at 0 |
| PASS | Inventory: missing price -> 'Add pack size & price' |
| PASS | Break-even with zero contribution -> 'Not reachable', no error |
| PASS | Event with variable costs >= 100% -> break-even 'n/a', loss verdict |
| PASS | Dashboard counts bad rows (recipes 4, sales 5, expenses 2, waste 1) |

## High volume

| Result | Check |
|---|---|
| PASS | 3,000 sales + 1,500 expenses + 50 menu items: zero errors (LibreOffice 4.7s) |
| PASS | Monthly revenue matches for all 12 months |
| PASS | Annual COGS and opex totals |
