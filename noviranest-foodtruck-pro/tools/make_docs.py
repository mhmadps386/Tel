"""Build the customer PDFs: Quick-Start Guide, Feature Overview, FAQ.

python tools/make_docs.py RENDER_DIR OUT_DIR
"""
import sys
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_workbook import RELEASE_DATE, VERSION  # noqa: E402

R, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_img"
TMP.mkdir(exist_ok=True)
for w in ("Regular", "Medium", "SemiBold", "Bold", "Italic"):
    pdfmetrics.registerFont(TTFont(f"Inter-{w}", str(ROOT / f"assets/fonts/Inter-{w}.ttf")))

INK, TEAL, AMBER, MUTED = colors.HexColor("#1E2A38"), colors.HexColor("#0F766E"), colors.HexColor("#C2770E"), colors.HexColor("#5B6573")
CREAM, GREY, INFO, LINE = colors.HexColor("#FFF6E0"), colors.HexColor("#F3F5F7"), colors.HexColor("#EAF2FB"), colors.HexColor("#DDE2E7")

S = {
    "h1": ParagraphStyle("h1", fontName="Inter-Bold", fontSize=24, leading=29, textColor=INK, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName="Inter-Bold", fontSize=15, leading=19, textColor=INK, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName="Inter-SemiBold", fontSize=11.5, leading=15, textColor=TEAL, spaceBefore=8, spaceAfter=3),
    "body": ParagraphStyle("body", fontName="Inter-Regular", fontSize=9.8, leading=14.2, textColor=INK, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Inter-Regular", fontSize=8.3, leading=11.5, textColor=MUTED),
    "bullet": ParagraphStyle("bullet", fontName="Inter-Regular", fontSize=9.8, leading=14, textColor=INK, leftIndent=12,
                             bulletIndent=2, spaceAfter=2.5, bulletFontName="Inter-Regular"),
    "cell": ParagraphStyle("cell", fontName="Inter-Regular", fontSize=8.8, leading=12, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Inter-SemiBold", fontSize=8.8, leading=12, textColor=INK),
    "kicker": ParagraphStyle("kicker", fontName="Inter-Bold", fontSize=9, leading=12, textColor=TEAL, spaceAfter=4),
    "caption": ParagraphStyle("caption", fontName="Inter-Italic", fontSize=8, leading=11, textColor=MUTED, alignment=TA_CENTER, spaceAfter=8),
}


def P(t, s="body"):
    return Paragraph(t, S[s])


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def img(name, width_mm, crop=None, caption=None):
    im = Image.open(R / f"{name}.png").convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
    p = TMP / f"{name}_{abs(hash(crop)) % 10000}.jpg"
    im.save(p, quality=88)
    w = width_mm * mm
    h = w * im.height / im.width
    flow = [RLImage(str(p), width=w, height=h)]
    if caption:
        flow.append(P(caption, "caption"))
    return KeepTogether(flow)


def box(text, fill=INFO, fg="#1E4E8C"):
    t = Table([[Paragraph(text, ParagraphStyle("b", parent=S["body"], textColor=colors.HexColor(fg), spaceAfter=0))]],
              colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), fill), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), S["cellb" if (header and i == 0) else "cell"]) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        for c in range(len(rows[0])):
            data[0][c] = Paragraph(str(rows[0][c]), ParagraphStyle("hh", parent=S["cellb"], textColor=colors.white))
        t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle(st))
    return t


def deco(title):
    def on_page(c, doc):
        c.saveState()
        c.setFillColor(TEAL)
        c.rect(0, A4[1] - 5, A4[0], 5, stroke=0, fill=1)
        c.setFont("Inter-Bold", 8)
        c.setFillColor(TEAL)
        c.drawString(20 * mm, A4[1] - 13 * mm, "NoviraNest")
        c.setFont("Inter-Regular", 8)
        c.setFillColor(MUTED)
        c.drawRightString(A4[0] - 20 * mm, A4[1] - 13 * mm, title)
        c.drawString(20 * mm, 11 * mm, f"Food Truck Profit & Pricing System PRO  ·  v{VERSION}")
        c.drawRightString(A4[0] - 20 * mm, 11 * mm, f"Page {doc.page}")
        c.restoreState()
    return on_page


def cover(title, subtitle, story):
    story += [Spacer(1, 30 * mm), P("NOVIRANEST", "kicker"),
              Paragraph(title, ParagraphStyle("ct", parent=S["h1"], fontSize=32, leading=38)),
              Spacer(1, 4 * mm), Paragraph(subtitle, ParagraphStyle("cs", parent=S["body"], fontSize=13, leading=19, textColor=MUTED)),
              Spacer(1, 10 * mm)]


def build(path, title, story):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm,
                            bottomMargin=18 * mm, title=title, author="NoviraNest", subject=f"Version {VERSION}")
    doc.build(story, onFirstPage=deco(title), onLaterPages=deco(title))
    print("wrote", path.name)


# =============================================================================================
# QUICK-START GUIDE
# =============================================================================================
s = []
cover("Quick-Start Guide", "Food Truck Profit &amp; Pricing System PRO<br/>Set up in about 30 minutes. No spreadsheet experience needed.", s)
s += [img("sample_01_Dashboard", 118, caption="The Dashboard of the SAMPLE file (fictional demo business)."),
      P(f"Version {VERSION} · {RELEASE_DATE} · For Microsoft Excel and Google Sheets", "small"), PageBreak()]

s += [P("1. Which file do I open?", "h1"),
      table([["File", "Use it for"],
             ["<b>…_TEMPLATE.xlsx</b>", "Your own business. Every log is empty. Start here."],
             ["<b>…_SAMPLE.xlsx</b>", "Exploring. A fictional demo truck with nine months of made-up data so you can see every feature working. "
                                      "Its numbers are <b>not</b> real results or benchmarks."]], [45, 125]),
      Spacer(1, 4 * mm),
      P("Opening in Microsoft Excel", "h3"),
      *bullets(["Double-click the file. If Excel shows <i>Protected View</i> or <i>Enable Editing</i>, click <b>Enable Editing</b> "
                "(the file has no macros).",
                "Save a copy with your business name: <b>File › Save As</b>."]),
      P("Opening in Google Sheets", "h3"),
      *bullets(["Go to <b>drive.google.com › New › File upload</b> and choose the TEMPLATE .xlsx.",
                "Open it, then choose <b>File › Save as Google Sheets</b>. Work in the new Google Sheets copy.",
                "Alternatively: in Google Sheets, <b>File › Import › Upload</b> and choose <i>Replace spreadsheet</i>.",
                "See section 6 for the small differences you will notice in Google Sheets."]),
      P("What the colours mean", "h3"),
      table([["Colour", "Meaning"],
             ["Cream cell, blue text", "<b>Type here.</b> The only cells you need to fill in."],
             ["Grey cell", "Automatic formula. Please don't type over it."],
             ["Red / pink", "Needs attention: loss-making item, unit mismatch, a row with a problem."],
             ["Blue box", "Instructions."]], [45, 125]),
      Spacer(1, 3 * mm),
      box("Tip: every sheet has navigation links under its title (› Start Here, › Dashboard…). The <b>Start Here</b> sheet "
          "inside the workbook repeats this guide in short form."),
      PageBreak()]

s += [P("2. Set up in six steps", "h1"),
      P("Step 1 · Settings", "h2"),
      *bullets(["<b>Business name</b> - shown on the Dashboard.",
                "<b>Currency</b> - USD ($) or GBP (£). Only symbols change; amounts are never converted.",
                "<b>Reporting year</b> and <b>Dashboard period</b> (Full Year or one month).",
                "<b>Labour cost per hour</b> - used only to price prep time on menu items.",
                "<b>Target profit margin</b> (e.g. 60%) and <b>Target food cost %</b> (e.g. 30%).",
                "<b>Round suggested prices up to</b> - e.g. 0.25 gives prices like 9.25, 9.50.",
                "<b>Last stock count date</b> - leave blank until you do your first stock count."]),
      img("sample_02_Settings", 130, crop=(0, 0, 1, 0.62)),
      P("Step 2 · Inventory - your ingredients", "h2"),
      *bullets(["One row per ingredient. Pick the <b>stock unit</b> you count it in (kg, lb, each, l, gal…).",
                "<b>Pack size</b> = how many stock units in one pack you buy (a 10 lb case → 10). <b>Pack price</b> = what you pay.",
                "Cost per stock unit is calculated for you.",
                "Optional now, useful later: opening stock, purchases since count, reorder level."]),
      PageBreak(),
      P("Step 3 · Menu item names, then the Recipe Builder", "h2"),
      *bullets(["On <b>Menu Pricing</b>, type your menu item names in column B (one per row).",
                "On <b>Recipe Builder</b>, add one row for each ingredient in ONE serving: menu item, ingredient, quantity, unit.",
                "You can use any unit of the same type as the ingredient's stock unit: stock in lb, recipe in oz; stock in l, recipe in ml or tbsp.",
                "If the units cannot be converted (e.g. 'each' and 'g'), the row shows <b>Unit mismatch</b> in red and is "
                "<b>not</b> costed. Weight ↔ volume conversions are never guessed."]),
      img("sample_04_Recipe_Builder", 165, crop=(0, 0, 1, 0.45)),
      box("Short on time? Skip recipes and type an <b>Ingredient override</b> (cost per serving) directly on Menu Pricing. "
          "You can build recipes later. Inventory usage is only tracked for items with recipes."),
      P("Step 4 · Menu Pricing", "h2"),
      *bullets(["Add <b>packaging</b>, <b>prep minutes</b>, <b>other variable cost</b> per serving and <b>your menu price</b>.",
                "Read the result: suggested price, profit per serving, <b>margin</b> (profit ÷ price), <b>markup</b> (profit ÷ cost), "
                "food cost % and a status with a recommendation.",
                "Status meanings: <b>LOSS</b> (price below cost) · <b>Below target</b> margin · <b>High food cost</b> · <b>Healthy</b>."]),
      PageBreak(),
      img("sample_03_Menu_Pricing", 170, crop=(0, 0, 1, 0.75), caption="Menu Pricing in the SAMPLE file."),
      P("Step 5 · Break-Even budget", "h2"),
      *bullets(["On <b>Break-Even</b>, type the monthly costs that do not change with each item sold: rent/commissary, truck payment, "
                "insurance, permits (monthly share), planned wages, typical fuel.",
                "Do <b>not</b> include ingredients or packaging - they are already in the cost per item.",
                "Optionally type the % of sales lost to card fees or commissions, your trading days per month and a profit goal."]),
      P("Step 6 · Start logging", "h2"),
      table([["Sheet", "When", "What to enter"],
             ["Sales Log", "Daily (or per event)", "Date, menu item, quantity. Price charged only if different from the menu price. "
                                                   "Location/event name if you want event reports."],
             ["Expenses", "When you pay", "Date, category, amount. Ingredient purchases and owner's draw can be logged - they are "
                                          "kept for your records but excluded from profit."],
             ["Waste Log", "When you throw food away", "Date, ingredient, quantity and unit, reason."]], [30, 35, 105]),
      Spacer(1, 3 * mm),
      box("Rows with a red <b>Check</b> are not counted until fixed. The Dashboard's <i>Alerts &amp; data checks</i> panel tells you "
          "how many rows need attention.", fill=colors.HexColor("#FDECEC"), fg="#B42318"),
      PageBreak()]

s += [P("3. Reading the Dashboard", "h1"),
      img("sample_01_Dashboard", 120),
      table([["Card", "What it means"],
             ["Total revenue", "Items sold × price charged, for the Dashboard period."],
             ["Gross profit", "Revenue − cost of goods sold (ingredients + packaging + other variable cost). Labour is not in COGS."],
             ["Net profit", "Gross profit − waste − operating expenses. Before income tax."],
             ["Net profit margin", "Net profit ÷ revenue."],
             ["Monthly operating expenses", "For a month period: that month. For the full year: average per month with activity."],
             ["Waste", "Value of food logged on the Waste Log."],
             ["Break-even progress", "Revenue ÷ break-even revenue for the period (needs Step 5)."]], [45, 125]),
      Spacer(1, 3 * mm),
      P("Switch <b>Settings › Dashboard period</b> to a month to see that month's cards and best sellers. The monthly chart always shows "
        "the full reporting year.", "body"),
      PageBreak()]

s += [P("4. Planning tools", "h1"),
      P("Event Profit Predictor", "h2"),
      *bullets(["Enter attendance, % of people who buy, orders per customer and average order value for worst / base / best case.",
                "Enter the event's costs once: pitch fee, commission %, card %, food cost %, staff, hours, wage, travel, fuel, other.",
                "Read estimated profit, <b>break-even orders</b>, break-even attendance and the risk verdict.",
                "After the event, log its sales with <b>Location = the exact event name</b>. Actual revenue, items and COGS appear "
                "automatically. Type the actual costs to see actual profit vs forecast.",
                "Forecasts never feed the Dashboard. Enter real event costs on Expenses so they count in your monthly profit."]),
      P("Scenario Simulator", "h2"),
      *bullets(["The baseline is your average month from the Sales Log and Expenses (or type your own baseline).",
                "Pick a preset (ingredient inflation, price increase, busy/slow season, wage rise, event fees, perfect storm) or "
                "choose <i>Custom</i> and type your own % changes.",
                "See revenue, gross profit, net profit and break-even change - and the <b>average price needed to keep today's "
                "profit</b>. Nothing on your other sheets changes."]),
      P("Break-Even Calculator", "h2"),
      *bullets(["Contribution per item = average price − average item cost − % fees.",
                "Break-even items = monthly fixed costs ÷ contribution per item (rounded up).",
                "Margin of safety compares your actual average items per month with break-even."]),
      PageBreak()]

s += [P("5. Your routine", "h1"),
      table([["How often", "Task", "Time"],
             ["Daily", "Log sales (one row per item per day is enough).", "2-5 min"],
             ["Weekly", "Log expenses and waste. Glance at Dashboard alerts.", "10 min"],
             ["When supplier prices change", "Update pack price on Inventory. Menu costs, suggested prices and statuses update.", "2 min"],
             ["Monthly", "Review the Dashboard and Monthly Report. Check items marked Below target / LOSS.", "15 min"],
             ["Stock count", "See below.", "30 min"]], [38, 110, 22]),
      P("Doing a stock count", "h3"),
      *bullets(["Count what you have. On Inventory, type the counted amounts into <b>Opening stock at count</b>.",
                "Clear <b>Purchased since count</b> and <b>Other usage</b> (set to 0).",
                "In Settings, set <b>Last stock count date</b> to the count date.",
                "From then on, usage from sales and waste after that date is deducted automatically. Add deliveries to "
                "<b>Purchased since count</b> as they arrive."]),
      P("Need more rows?", "h3"),
      P("Logs come pre-built with 3,000 sales rows, 1,500 expense rows, 500 waste rows, 400 recipe lines, 100 ingredients and "
        "50 menu items. At one row per item per day, 3,000 sales rows cover roughly a year for a 10-item menu. Start a new copy "
        "of the TEMPLATE each year (recommended), or insert rows <i>inside</i> a table (not below it) so formulas and ranges "
        "extend automatically - then copy a formula row into the new rows."),
      PageBreak()]

s += [P("6. Google Sheets notes", "h1"),
      P("The workbook was designed for both apps and avoids Excel-only functions. When opened in Google Sheets:"),
      *bullets(["<b>Currency symbols:</b> in Excel, money cells show $ or £. Google Sheets cannot change number formats "
                "conditionally, so money cells show plain numbers; the currency symbol appears in column headers and on all "
                "Dashboard cards. Switching USD/GBP still works.",
                "<b>Charts</b> are converted by Google and may look slightly different (colours, label positions).",
                "<b>Navigation links</b> between sheets may need a click on the sheet tab instead if a link does not jump.",
                "<b>Protected Dashboard:</b> Google may show a warning if you try to edit it - that is intended.",
                "Dropdowns, input messages, formulas and conditional colours work the same way.",
                "Dates and numbers follow your Google account's locale (File › Settings)."]),
      P("7. Troubleshooting", "h1"),
      table([["You see…", "Do this"],
             ["Check: <i>Item not on Menu Pricing</i>", "Spelling must match exactly. Use the dropdown."],
             ["Check: <i>Enter a valid date</i>", "Type a real date in your computer's date format, e.g. 15/03/2026 (UK) or 3/15/2026 (US)."],
             ["Unit check: <i>Unit mismatch</i>", "Pick a unit of the same type as the ingredient's stock unit (mass, volume or count)."],
             ["Status: <i>Add costs</i>", "Build the recipe or type an ingredient override for the item."],
             ["Inventory: <i>Recount (negative)</i>", "Usage exceeded stock: do a stock count (section 5) or add missing purchases."],
             ["Dashboard all zeros", "Check Settings › Reporting year matches your sales dates."],
             ["Break-even progress shows <i>Set up</i>", "Enter monthly fixed costs on Break-Even."]], [60, 110]),
      Spacer(1, 4 * mm),
      box("This workbook gives management estimates. It is not tax, legal or accounting advice. Keep your official records "
          "with your accountant or bookkeeping software."),
      Spacer(1, 4 * mm),
      P(f"© NoviraNest. Licensed for use by one business. Please do not share or resell the files. Version {VERSION}.", "small")]
build(OUT / "NoviraNest_Quick_Start_Guide.pdf", "Quick-Start Guide", s)

# =============================================================================================
# FEATURE OVERVIEW
# =============================================================================================
s = []
cover("Feature Overview", "Food Truck Profit &amp; Pricing System PRO - what every sheet does and how every number is calculated.", s)
s += [img("sample_01_Dashboard", 118), PageBreak(),
      P("The 7 tools", "h1"),
      table([["Tool", "What you get"],
             ["Executive Dashboard", "Revenue, gross profit, net profit, net margin, monthly operating expenses, COGS, waste, break-even "
                                     "progress; monthly revenue/gross/net chart; where-the-money-goes chart; top-5 best sellers; top-5 "
                                     "most profitable items; 8 alert counters."],
             ["Smart Menu Pricing", "Ingredient cost per serving (from recipes or override), packaging, prep labour (minutes × rate), other "
                                    "variable cost, total cost, target margin, suggested price (rounded up), profit, actual margin, markup, "
                                    "food cost %, status, recommendation, items sold / revenue / gross profit / sales mix per item."],
             ["Recipe Builder", "400 ingredient lines. 18 units (g, kg, oz, lb, ml, l, tsp, tbsp, US cup, US/UK fl oz, US/UK pint, US/UK gal, "
                                "each, dozen, portion). Converts within mass, volume or count; flags mismatches."],
             ["Inventory & Waste", "100 ingredients: cost per stock unit, opening stock, purchases, automatic usage from sales, other usage, "
                                   "waste, estimated on hand, stock value, reorder alerts. Waste Log valued with unit conversion."],
             ["Sales & Expenses", "3,000 sales rows and 1,500 expense rows with automatic revenue, COGS, gross profit, cost type and row "
                                  "checks; Monthly Report P&amp;L for 12 months; expenses by category."],
             ["Break-Even Calculator", "Fixed-cost budget, contribution per item, contribution margin ratio, break-even items / revenue / items "
                                       "per day, target-profit items and revenue, margin of safety, chart."],
             ["Event Profit Predictor", "Worst / base / best demand, event costs, revenue, contribution, profit, margin, break-even orders and "
                                        "attendance, verdict, actual results from your logs and variance vs forecast."],
             ["Scenario Simulator", "Baseline month from your data (or override), 5 levers, 9 editable presets, impact table, break-even change, "
                                    "price needed to keep baseline profit, chart."]], [40, 130]),
      PageBreak(),
      P("How the numbers work", "h1"),
      table([["Measure", "Formula", "Notes"],
             ["Revenue", "Σ qty × price charged", "Menu price unless a different price is typed on the Sales Log"],
             ["COGS", "Σ qty × (ingredient + packaging + other variable cost per serving)", "Standard cost from current Menu Pricing costs; excludes labour"],
             ["Gross profit / margin", "Revenue − COGS;  ÷ Revenue", ""],
             ["Waste", "Σ waste qty (in stock units) × cost per stock unit", "Counted once, as its own line"],
             ["Operating expenses", "Expenses of type Fixed + Labor + Event Fees + Variable", "Stock purchases and owner's draw excluded"],
             ["Net profit / margin", "Gross profit − Waste − Operating expenses;  ÷ Revenue", "Before income tax"],
             ["Suggested price", "Total cost ÷ (1 − target margin), rounded up", "Total cost includes prep labour allowance"],
             ["Margin", "(Price − cost) ÷ price", ""],
             ["Markup", "(Price − cost) ÷ cost", "Cost 4, price 10 → margin 60%, markup 150%"],
             ["Food cost %", "Ingredient cost ÷ price", ""],
             ["Unit conversion", "qty × factor(recipe unit) ÷ factor(stock unit)", "Only if both units have the same dimension"],
             ["Stock on hand", "Opening + purchased − used by sales − other − waste", "Usage and waste counted from the stock-count date"],
             ["Break-even items", "Fixed costs ÷ (price − item cost − price × fee %), rounded up", ""],
             ["Event break-even orders", "Fixed event costs ÷ (AOV × (1 − food% − commission% − card%)), rounded up", ""]], [35, 75, 60]),
      Spacer(1, 4 * mm),
      P("Assumptions you should know", "h2"),
      *bullets(["COGS uses the <b>current</b> recipe and packaging costs. If supplier prices change, past months are re-valued at the new "
                "cost (standard costing). Export or save a copy at month end if you need frozen history.",
                "Labour in Menu Pricing is a pricing allowance; actual wages come only from Expenses.",
                "Inventory usage is theoretical (recipe × items sold). Real usage differs - regular stock counts correct it.",
                "The Scenario Simulator treats wages, event fees, other operating costs and waste as monthly amounts; price changes do not "
                "change volume unless you also move the volume lever.",
                "Currency setting changes symbols only. No exchange rates are used.",
                "No taxes (sales tax / VAT, income tax) are calculated. Record sales net of sales tax/VAT for accurate margins."]),
      PageBreak(),
      P("Technical specifications", "h1"),
      table([["Item", "Detail"],
             ["Files", "TEMPLATE (empty) and SAMPLE (fictional demo) .xlsx workbooks; 14 worksheets each"],
             ["Compatibility", "Microsoft Excel 2010 or later (Windows/Mac) and Google Sheets. Uses only long-established functions (SUMIFS, "
                               "INDEX/MATCH, SUMPRODUCT, IFERROR…); no macros, VBA, add-ins, external links or dynamic-array functions."],
             ["Capacity", "50 menu items · 400 recipe lines · 100 ingredients · 500 waste rows · 3,000 sales rows · 1,500 expense rows"],
             ["Currencies", "USD ($) and GBP (£)"],
             ["Protection", "Dashboard protected without a password (to prevent accidental edits). Other sheets are open."],
             ["Testing", "Every calculation was recalculated by a spreadsheet engine and compared with independent calculations; "
                         "edge cases (empty, invalid, zero, negative, unit mismatch) and a full-capacity data set were tested."]], [35, 135]),
      Spacer(1, 4 * mm),
      P("Known limitations", "h2"),
      *bullets(["One reporting year at a time (start a new copy each year, or change the reporting year to view another).",
                "Weight ↔ volume conversions (e.g. grams of flour to cups) need a density and are deliberately not supported - use the same "
                "unit type as the stock unit.",
                "In Google Sheets, money cells show plain numbers (symbol in headers and Dashboard cards).",
                "Not a bookkeeping, payroll or tax system."])]
build(OUT / "NoviraNest_Feature_Overview.pdf", "Feature Overview", s)

# =============================================================================================
# FAQ
# =============================================================================================
faq = [
    ("Do I need Excel?", "No. You can use Microsoft Excel (2010 or later, Windows or Mac) or Google Sheets with a free Google account."),
    ("Does it use macros?", "No. There are no macros, VBA, add-ins or external connections, so it opens without security prompts beyond "
                            "Excel's normal 'Enable Editing' for downloaded files."),
    ("Which file should I use?", "Use the TEMPLATE for your business. The SAMPLE file is a fictional demo for learning - its numbers are "
                                 "invented and are not industry benchmarks."),
    ("Can I use it in the UK?", "Yes. Choose GBP in Settings. Symbols change to £; amounts are not converted. UK fluid ounces, pints and "
                                "gallons are included as units."),
    ("Why is my ingredient purchase not reducing my profit?", "Because the food you <i>used</i> is already counted in cost of goods sold "
                                                               "(recipe cost × items sold). Counting purchases as well would count the same food "
                                                               "twice. Purchases stay in Expenses for your records."),
    ("Why is labour on Menu Pricing not in gross profit?", "Prep labour on Menu Pricing helps you set a price that covers your time. Your real "
                                                           "wages are entered on Expenses and reduce net profit once."),
    ("What is the difference between margin and markup?", "Margin = profit ÷ price. Markup = profit ÷ cost. An item costing 4.00 sold for "
                                                          "10.00 has a 60% margin and a 150% markup. The workbook shows both."),
    ("My recipe line says 'Unit mismatch'.", "The recipe unit and the ingredient's stock unit measure different things (e.g. 'each' and "
                                             "'g'). Choose a unit of the same type, or change how you stock the ingredient."),
    ("Can I convert grams to cups?", "Not automatically - that needs the density of each ingredient. Enter the recipe in the same type of unit "
                                     "as the stock unit (weight with weight, volume with volume)."),
    ("Do I have to use the Recipe Builder?", "No. Type an ingredient cost per serving in 'Ingredient override' on Menu Pricing. Recipes add "
                                             "automatic cost updates and inventory tracking."),
    ("Is the inventory exact?", "It is an estimate: recipe quantities × items sold, plus waste. Do regular stock counts to correct it "
                                "(see the Quick-Start Guide)."),
    ("Do event forecasts affect my profit figures?", "No. Forecasts stay on the Event Predictor. Only your Sales Log and Expenses drive the "
                                                     "Dashboard."),
    ("Can I add more expense categories or units?", "Yes - type them into the empty cream rows on the Lists sheet and choose a cost type."),
    ("What if I run out of rows?", "3,000 sales rows cover about a year for a typical menu at one row per item per day. Start a new copy "
                                   "each year, or insert rows inside the table and copy a formula row into them."),
    ("Does it calculate tax or VAT?", "No. Enter sales without sales tax/VAT for accurate margins. It is a management tool, not tax advice."),
    ("Can I share it with my business partner?", "Yes, within your own business. The licence covers one business; please don't share it "
                                                 "publicly or resell it."),
    ("Will I get updates?", "If an update is released, it is delivered through the platform you bought from (Etsy or Gumroad downloads)."),
    ("Something looks wrong.", "Check the Dashboard's Alerts panel first - rows with problems are not counted. If it is still wrong, contact "
                               "us through the platform's messaging with a description (please don't send your business data unless needed)."),
]
s = []
cover("Customer FAQ", "Answers to the most common questions about Food Truck Profit &amp; Pricing System PRO.", s)
s += [PageBreak()]
for q_, a_ in faq:
    s.append(KeepTogether([P(q_, "h3"), P(a_)]))
build(OUT / "NoviraNest_Customer_FAQ.pdf", "Customer FAQ", s)
import shutil  # noqa: E402
shutil.rmtree(TMP)
