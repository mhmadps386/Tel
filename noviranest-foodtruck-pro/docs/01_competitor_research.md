# Phase 1 — Competitor Research & Differentiation

Research date: 2026-10-26. Method: web search of Etsy, Gumroad and independent template sellers.

## Evidence limits (read first)

- Etsy listing pages and Etsy search pages returned **HTTP 403** to automated fetches, so Etsy evidence
  comes from **search-engine snippets of listing titles/descriptions**, not from opening the files.
- We did **not** buy or open any competitor file. Statements about competitor formulas, accuracy or
  usability are therefore *not* made. Comparisons below are limited to **advertised** features and prices.
- Prices are snapshots from snippets and change frequently (Etsy sales are common).

## What was found

| Product (source) | Advertised scope | Advertised price | Notes |
|---|---|---|---|
| Etsy "food truck pricing spreadsheet" (search snippet) | Menu cost & profit calculator | ~$9 | Single-purpose pricing tool |
| Etsy "Food Truck Business Tracker" listings (e.g. listing 4482053908, 4520885117) | Dashboard, event log, menu & margins, fixed expenses, monthly P&L; one claims 18 sheets incl. booking calendar and route profit | ~$11.99–$14.49 (sale prices seen) | Closest competitors in scope |
| Etsy "Food Truck Template, Google Sheets" (listing 4476687375) | Menu costing, daily sales logs, inventory, expenses, locations, prep planning | not captured | Google Sheets only |
| Etsy "Food truck bookkeeping spreadsheet" (market page) | Sales, event profit, COGS, expenses, net profit columns | ~$3–$22 range across listings | Bookkeeping focus |
| Etsy recipe/food cost calculators (listings 1620705067, 1367626909, 1890030047) | Recipe/portion cost, profit margin | ~$4–$25 | Restaurant-generic, not truck/event specific |
| Etsy "Food Truck Business Income Statement Generator" (1394762829) | Automated P&L, 5-year | not captured | Projection, not operations |
| Someka Food Cost Calculator (someka.net) | 4 sheets: Dashboard, Raw Materials, Meals Ingredients, Sales Summary; up to 400 recipes; unit dropdown | Free demo + paid license (price not shown); 4.58/5 from 12 reviews on their site | Page does not mention unit **conversion**; a reviewer reported accidentally deleting a formula |
| Loomiq Studio recipe cost calculator (Gumroad) | Recipe sheet, ingredient unit costs, cost factors (labor, packaging, delivery) | not captured | Mentions food trucks as a target user |
| Pat Flynn "Food Truck Growth Kit" (Gumroad) | Book + worksheets + printables | not captured | Planning content, not a calculator |
| SharpSheets Food Truck Financial Model | 5-year projections, 3 statements, valuation | $119 (from $179) | Investor/startup model, not daily operations |
| eFinancialModels Food Truck model | Traffic, AOV, sales mix, startup costs, low/base/high scenarios | not captured | Startup projection model |
| FoodCostChef / Sheetrix (free) | Recipe costing; markup multiplier → suggested price | Free | Free alternatives set a price floor for simple tools |

Sources: etsy.com/market/food_truck_spreadsheet, etsy.com/market/food_truck_bookkeeping_spreadsheet,
etsy.com/listing/4520885117, etsy.com/nz/listing/4476687375, etsy.com/in-en/listing/4482053908,
someka.net/products/food-cost-google-sheets-template, loomiqstudio.gumroad.com, patflynn.gumroad.com/l/foodtruckgrowth,
sharpsheets.io/templates/food-truck-financial-model, efinancialmodels.com, foodcostchef.com, sheetrix.com.

## Market observations

1. **Two clusters:** cheap operational trackers ($3–$15 on Etsy) and expensive startup projection
   models ($100+). Few products sit in between as an *operational decision tool*.
2. **Gumroad has little food-truck-specific spreadsheet supply** (searches surfaced generic recipe
   costers and info products) — a less crowded channel.
3. Advertised features rarely mention: unit conversion between purchase and recipe units, a defined
   accounting model (what is in COGS vs operating expenses), forecast-vs-actual for events, or
   non-destructive what-if simulation. Absence from a listing is **not proof** a product lacks it.
4. Several products are Google-Sheets-only or Excel-only.

## NoviraNest differentiators (each is verifiable in our own file)

1. **Recipe-linked costing with unit conversion and a mismatch guard.** Buy in kg/lb/gal/each, use in
   g/oz/ml/tsp — the workbook converts within the same dimension and refuses to combine
   incompatible units (e.g. "each" with "g"), flagging the line instead of silently producing a wrong cost.
2. **One consistent accounting model with no double counting.** COGS = recipe cost × items sold
   (ingredients + packaging + other variable cost); labour lives only in operating expenses;
   stock purchases and owner draws are logged but excluded from profit; waste is counted once.
   Documented on the Start Here sheet.
3. **Event Profit Predictor with worst/base/best, break-even orders and forecast-vs-actual.**
   Actual event revenue is pulled automatically from the Sales Log by event name.
4. **Theoretical inventory depletion.** Stock on hand falls automatically as items are sold (via
   recipes) and as waste is logged — no manual usage counting required.
5. **Non-destructive Scenario Simulator with presets** (inflation, price rise, busy/slow season,
   wage rise) and a "price needed to keep today's profit" answer.
6. **USD and GBP** formatting for US & UK sellers without fake exchange-rate conversion.
7. **Excel + Google Sheets** from the same file, with compatibility limits disclosed rather than hidden.

We do **not** claim superiority on accuracy or ease of use versus named competitors — we have not
tested their files.

## Pricing hypothesis

- Etsy operational trackers cluster ~$9–$15 (often discounted); startup models $100+.
- NoviraNest PRO scope (7 tools + recipe engine + docs) supports a **$29 list price**, with an Etsy
  launch sale to ~$19–$22 to gather first reviews. Gumroad: $29 with optional "pay what you want" floor
  disabled. Re-evaluate after 30 days of conversion data.
