# Phase 1 — Product Architecture & Calculation Specification

## Worksheets (in tab order)

| Tab | Purpose | Feeds |
|---|---|---|
| Start Here | Welcome, 6-step setup, colour legend, sheet directory, definitions | — |
| Dashboard | KPI cards, charts, best sellers, most profitable items, alerts | read-only |
| Settings | Business name, currency, reporting year, dashboard period, labour rate, targets, rounding, stock-count date | everything |
| Menu Pricing | Cost per serving, suggested price, actual margin/markup/food cost %, status & recommendation, item sales performance | Sales Log, Dashboard |
| Recipe Builder | Ingredient lines per menu item with unit conversion → ingredient cost per serving, theoretical usage | Menu Pricing, Inventory |
| Inventory | Ingredient master: pack price → cost per stock unit; on-hand = opening + purchased − used − other − waste; value; reorder alerts | Recipe Builder, Waste Log |
| Waste Log | Dated waste with unit conversion → waste value | Inventory, Monthly Report |
| Sales Log | Dated item sales → revenue, COGS, gross profit | everything |
| Expenses | Dated expenses with category → cost type | Monthly Report |
| Monthly Report | 12-month P&L for the reporting year, selected-period summary, expense breakdown | Dashboard, Break-Even, Simulator |
| Break-Even | Fixed-cost budget, contribution margin, break-even items/revenue, target profit, chart | Dashboard |
| Event Predictor | Worst/base/best forecast for one event + actual results vs forecast | standalone |
| Scenario Simulator | Baseline (from data or override) × levers/presets → impact, no input changed | standalone |
| Lists | Units & conversion factors, expense categories & cost types, dropdown lists | everything |

## Cell conventions

- **Input** (cream fill, blue text): the only cells a user types into.
- **Calculated** (light grey fill, dark text): formulas — do not type over.
- **Warning** (red text on pink): problems that change results.
- **Info** (blue on pale blue): instructions.
- Every calculated column returns `""` on empty rows so logs look clean and no `#DIV/0!` appears.

## Accounting model (single source of truth — no double counting)

| Term | Formula | Notes |
|---|---|---|
| Revenue | Σ qty × price charged | price = override in Sales Log, else Menu price |
| COGS (standard) | Σ qty × (ingredient + packaging + other variable cost per serving) | **excludes labour**; uses current Menu Pricing costs |
| Gross profit | Revenue − COGS | |
| Gross margin | Gross profit ÷ Revenue | blank when revenue = 0 |
| Waste | Σ waste qty (converted to stock unit) × cost per stock unit | counted once, as its own P&L line |
| Operating expenses | Expenses of type Fixed + Labor + Event Fees + Variable | |
| Excluded | "Stock purchase" (ingredient/packaging purchases) and "Owner draw" | logged for cash records, **not** in profit — COGS already covers food used |
| Net profit | Gross profit − Waste − Operating expenses | before income tax |
| Net margin | Net profit ÷ Revenue | |

Labour in Menu Pricing (prep minutes × hourly rate) is a **pricing allowance only**; real wages are
entered in Expenses. It never enters COGS → labour is counted once.

## Pricing math

- Total cost per serving `C` = ingredient + packaging + prep labour + other variable.
- Suggested price `P* = C ÷ (1 − target margin)`, rounded **up** to the chosen step (or 2 dp).
- Profit per serving = Price − C.
- **Margin** = Profit ÷ Price. **Markup** = Profit ÷ C. (Example: C = 4, Price = 10 → margin 60 %, markup 150 %.)
- **Food cost %** = ingredient cost ÷ price.
- Status priority: Set a price → Add costs → LOSS (price < cost) → Below target margin → High food cost → Healthy.

## Unit conversion

Each unit has a dimension (mass, volume, count) and a factor to the base unit (g, ml, each).
`qty_in_stock_unit = qty × factor(recipe unit) ÷ factor(stock unit)` — only when dimensions match;
otherwise the line is flagged **Unit mismatch** and contributes 0 cost (visible warning, not a silent number).
US and UK fluid ounces are separate units. No density conversions (weight ↔ volume) are attempted.

## Inventory

- Cost per stock unit = pack price ÷ pack size (pack size expressed in stock units).
- Used by sales = Σ over recipe lines (qty in stock units × items sold since the last stock count date).
- On hand = opening (at count) + purchased since count − used by sales − other usage − waste since count.
- Value = max(0, on hand) × cost per stock unit. Reorder when on hand ≤ reorder level; negative → "Recount".

## Break-even

- Contribution per item = avg price − avg COGS per item − avg price × other variable %.
- Break-even items = ⌈fixed ÷ contribution⌉; break-even revenue = fixed ÷ (contribution ÷ price).
- Target-profit items = ⌈(fixed + target) ÷ contribution⌉.
- Averages come from the Sales Log (reporting year) unless overridden.
- Fixed costs come from the **budget** on the Break-Even sheet (planning), shown next to the actual monthly average.

## Event Predictor (forecast, never mixed with actuals)

customers = attendance × buy rate; orders = round(customers × orders per customer); revenue = orders × AOV;
variable = revenue × (food % + commission % + card %); fixed event costs = fee + staff × hours × wage + transport + fuel + other;
profit = revenue − variable − fixed; break-even orders = ⌈fixed ÷ (AOV × (1 − variable %))⌉.
Actual section pulls revenue/items/COGS from the Sales Log where Location = event name; costs are typed in.

## Scenario Simulator

Baseline monthly averages over months with sales in the reporting year (or overrides). Levers: ingredient
price %, sales volume %, menu price %, labour %, event fee %. Presets selectable; "Custom" uses typed levers.
Waste scales with ingredient prices. Output: baseline vs scenario P&L, change, break-even items and
the average price needed to keep baseline net profit. No source data is modified.

## Currency

Settings → USD or GBP. Headers and KPI cards show the symbol through formulas (works in Excel and Google Sheets).
In Excel, money cells also get a currency number format via conditional formatting. No exchange-rate conversion.
