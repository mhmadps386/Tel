"""Compose marketing preview images from REAL LibreOffice renders of the workbook (sample data).

python tools/make_previews.py RENDER_DIR OUT_DIR
Etsy: 3000x2250 (4:3). Gumroad: cover 1280x720, thumbnail 600x600.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

R, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
FD = "/usr/share/fonts/opentype/inter/"
INK, TEAL, AMBER, BG, MUTED, WHITE = "#1E2A38", "#0F766E", "#C2770E", "#F5F3EE", "#5B6573", "#FFFFFF"
TEAL_LIGHT = "#E3F1EF"


def f(size, w="Bold", display=False):
    return ImageFont.truetype(f"{FD}{'InterDisplay' if display else 'Inter'}-{w}.otf", size)


def shot(name):
    return Image.open(R / f"{name}.png").convert("RGB")


def crop_frac(im, l=0, t=0, r=1, b=1):
    w, h = im.size
    return im.crop((int(l * w), int(t * h), int(r * w), int(b * h)))


def window(canvas, im, box, title="", radius=22):
    """Paste screenshot into a box as an app-window card with shadow."""
    x0, y0, x1, y1 = box
    bar = 54
    bw, bh = x1 - x0, y1 - y0 - bar
    s = min(bw / im.width, bh / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    w, h = im.width, im.height + bar
    cx = x0 + (bw - im.width) // 2
    cy = y0
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((cx + 10, cy + 24, cx + w + 10, cy + h + 24), radius, fill=(30, 42, 56, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(28))
    canvas.alpha_composite(sh)
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=WHITE, outline="#D9DEE4", width=2)
    d.rounded_rectangle((0, 0, w - 1, bar + radius), radius, fill="#E9ECEF")
    d.rectangle((0, bar, w - 1, bar + radius), fill=WHITE)
    for i, c in enumerate(("#E5736B", "#E7B54E", "#5FB672")):
        d.ellipse((26 + i * 34, bar // 2 - 9, 44 + i * 34, bar // 2 + 9), fill=c)
    if title:
        d.text((w // 2, bar // 2), title, font=f(24, "Medium"), fill=MUTED, anchor="mm")
    card.paste(im, (0, bar))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius, fill=255)
    canvas.paste(card, (cx, cy), mask)
    return (cx, cy, cx + w, cy + h)


def base(w=3000, h=2250):
    c = Image.new("RGBA", (w, h), BG)
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, w, 14), fill=TEAL)
    return c, d


def brand(d, x=140, y=110, size=40):
    d.text((x, y), "NoviraNest", font=f(size, "Bold"), fill=TEAL)


def pill(d, xy, text, fg=INK, bg=WHITE, size=40, outline="#D9DEE4"):
    x, y = xy
    tw = d.textlength(text, font=f(size, "SemiBold"))
    d.rounded_rectangle((x, y, x + tw + 64, y + size + 44), (size + 44) // 2, fill=bg, outline=outline, width=2)
    d.text((x + 32, y + 22), text, font=f(size, "SemiBold"), fill=fg)
    return x + tw + 64


def footnote(d, w=3000, h=2250, text="Screens show the included SAMPLE file with fictional demo data  ·  Works in Microsoft Excel and Google Sheets"):
    d.text((w // 2, h - 70), text, font=f(32, "Medium"), fill=MUTED, anchor="mm")


def headline(d, title, sub, x=140, y=190, size=118, width=None):
    d.text((x, y), title, font=f(size, "Bold", True), fill=INK)
    if sub:
        d.text((x + 4, y + size + 40), sub, font=f(50, "Regular"), fill=MUTED)


def save(c, name):
    c.convert("RGB").save(OUT / name, quality=92)
    print(name, c.size)


def bullets(d, items, x, y, size=50, gap=150, width=820):
    for t, sub in items:
        d.ellipse((x, y + 14, x + 34, y + 48), fill=TEAL)
        d.text((x + 9, y + 8), "✓", font=f(26, "Bold"), fill=WHITE)
        d.text((x + 64, y), t, font=f(size, "SemiBold"), fill=INK)
        if sub:
            d.multiline_text((x + 64, y + size + 14), sub, font=f(34, "Regular"), fill=MUTED, spacing=8)
        y += gap
    return y


# 01 HERO ------------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Food Truck Profit &\nPricing System PRO", None, size=124)
d.multiline_text((144, 520), "Know your real profit per item,\nper event and per month.", font=f(54, "Regular"), fill=MUTED, spacing=12)
x = 140
for t in ("Excel + Google Sheets", "USD $ & GBP £"):
    x = pill(d, (x, 700), t, size=38) + 24
x = 140
for t in ("No macros", "Sample + clean template"):
    x = pill(d, (x, 810), t, size=38) + 24
window(c, shot("sample_01_Dashboard"), (1560, 120, 2900, 2120), "Executive Dashboard")
y = 1010
y = bullets(d, [("Smart menu pricing", "Margin, markup, food cost % and a\nsuggested price for every item"),
                ("Recipe costing with unit conversion", "Buy in lb or kg, use in oz or g"),
                ("Event profit predictor", "Worst / base / best case + break-even orders"),
                ("Break-even & scenario simulator", "Test price rises, inflation, slow seasons"),
                ("Inventory, waste, sales & expenses", "Monthly P&L built automatically")], 150, y, size=46, gap=205)
footnote(d)
save(c, "01_hero_3000x2250.jpg")

# 02 DASHBOARD -----------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Your whole business on one screen", "Revenue, gross & net profit, margins, best sellers, alerts - updated as you log sales.", size=100)
window(c, crop_frac(shot("sample_01_Dashboard"), 0, 0, 1, 1), (200, 520, 2800, 2140), "Dashboard")
footnote(d)
save(c, "02_dashboard_3000x2250.jpg")

# 03 MENU PRICING ----------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Price every menu item for profit", "Full cost per serving -> suggested price -> real margin. Loss-makers are flagged in red.", size=100)
mp = shot("sample_03_Menu_Pricing")
window(c, crop_frac(mp, 0, 0, 0.62, 0.70), (100, 450, 2900, 1600), "Smart Menu Pricing")
cards = [("Margin ≠ markup", "Both calculated correctly:\nmargin = profit / price\nmarkup = profit / cost"),
         ("Suggested price", "Set a target margin; the price is\nrounded up to your chosen step"),
         ("Clear status", "LOSS · Below target · High food cost\n· Healthy - with what to fix")]
for i, (t, s) in enumerate(cards):
    x0 = 140 + i * 920
    d.rounded_rectangle((x0, 1640, x0 + 860, 2060), 28, fill=WHITE, outline="#D9DEE4", width=2)
    d.rectangle((x0, 1640, x0 + 860, 1652), fill=TEAL if i < 2 else AMBER)
    d.text((x0 + 50, 1700), t, font=f(54, "Bold"), fill=INK)
    d.multiline_text((x0 + 50, 1790), s, font=f(38, "Regular"), fill=MUTED, spacing=12)
footnote(d)
save(c, "03_menu_pricing_3000x2250.jpg")

# 04 RECIPES + INVENTORY ---------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Recipe costing that understands units", "Buy in lb, kg, gallons or cases. Use in oz, g, ml or tbsp. The workbook converts it.", size=100)
window(c, crop_frac(shot("sample_04_Recipe_Builder"), 0, 0, 1, 0.62), (140, 520, 1880, 1720), "Recipe Builder")
window(c, crop_frac(shot("sample_05_Inventory"), 0, 0, 1, 0.55), (1000, 1260, 2880, 2110), "Inventory")
bullets(d, [("Units never mixed up", "'each' vs 'g' is flagged as a\nmismatch - never silently costed"),
            ("Stock falls as you sell", "Usage = recipe x items sold"),
            ("Reorder alerts", "Plus stock value & waste value")], 1990, 600, size=46, gap=230)
footnote(d)
save(c, "04_recipes_inventory_3000x2250.jpg")

# 05 EVENT ---------------------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Should you book\nthat event?", None, size=112)
d.multiline_text((144, 520), "Forecast worst, base and best case before\nyou pay the pitch fee - then compare with\nwhat actually happened.", font=f(48, "Regular"), fill=MUTED, spacing=14)
bullets(d, [("Break-even orders & attendance", "Know the minimum you must sell"),
            ("Risk verdict", "Low / moderate / high risk / not viable"),
            ("Forecast vs actual", "Actual revenue pulled from your\nSales Log by event name"),
            ("Kept separate", "Forecasts never mix with real results")], 150, 820, size=46, gap=250)
window(c, shot("sample_11_Event_Predictor"), (1420, 110, 2880, 2130), "Event Profit Predictor")
footnote(d)
save(c, "05_event_predictor_3000x2250.jpg")

# 06 BREAK-EVEN + SIMULATOR -------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Plan before costs rise", "Break-even targets and what-if scenarios - without touching your real data.", size=104)
window(c, shot("sample_10_Break-Even"), (140, 500, 1460, 2130), "Break-Even Calculator")
window(c, shot("sample_12_Scenario_Simulator"), (1540, 500, 2860, 2130), "Scenario Simulator")
footnote(d)
save(c, "06_breakeven_simulator_3000x2250.jpg")

# 07 NUMBERS YOU CAN TRUST ----------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Numbers you can trust", "One clear profit model. Nothing counted twice.", size=110)
steps = [("Revenue", "items sold x price charged", TEAL), ("- COGS", "recipe cost x items sold\n(food + packaging, no labour)", INK),
         ("= Gross profit", "", TEAL), ("- Waste", "from the Waste Log", INK),
         ("- Operating expenses", "fixed, labour, event fees, variable", INK), ("= Net profit", "before tax", AMBER)]
y = 560
for t, s, col in steps:
    d.rounded_rectangle((140, y, 1500, y + 210), 26, fill=WHITE, outline="#D9DEE4", width=2)
    d.rectangle((140, y, 158, y + 210), fill=col)
    d.text((210, y + 30 if s else 70), t, font=f(58, "Bold"), fill=col if col != INK else INK)
    if s:
        d.multiline_text((210, y + 106), s, font=f(32, "Regular"), fill=MUTED, spacing=6)
    y += 230
bullets(d, [("Labour counted once", "Prep time prices your menu; real\nwages live only in Expenses"),
            ("Stock purchases excluded", "Food used is already in COGS"),
            ("Owner's draw excluded", "It is not a business expense"),
            ("Margin vs markup", "Never confused - both shown"),
            ("Formula-tested", "Results checked against independent\ncalculations, plus empty, invalid\nand 3,000-row data")],
        1660, 580, size=48, gap=290)
footnote(d, text="Works in Microsoft Excel and Google Sheets  ·  No macros")
save(c, "07_numbers_you_can_trust_3000x2250.jpg")

# 08 UK / GBP ----------------------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "Selling in the UK? Switch to £", "One setting changes every symbol. Amounts are never converted with a made-up exchange rate.", size=104)
window(c, crop_frac(shot("sample_gbp_01_Dashboard"), 0, 0, 1, 0.53), (300, 520, 2700, 2140), "Dashboard - GBP")
footnote(d)
save(c, "08_usd_gbp_3000x2250.jpg")

# 09 WHAT'S INCLUDED -----------------------------------------------------------------------------
c, d = base()
brand(d)
headline(d, "What's included", "Instant digital download - no physical item is shipped.", size=112)
items = [("Excel workbook - TEMPLATE", "Clean, empty, ready for your business (.xlsx)"),
         ("Excel workbook - SAMPLE", "Fully filled fictional demo to explore every feature"),
         ("Google Sheets ready", "Open the .xlsx in Google Sheets - step-by-step guide included"),
         ("Quick-Start Guide (PDF)", "Set up in about 30 minutes"),
         ("Feature Overview & FAQ (PDF)", "How every number is calculated"),
         ("14 worksheets, 7 tools", "Dashboard · Menu Pricing · Recipe Builder · Inventory & Waste\nSales & Expenses · Break-Even · Event Predictor · Scenario Simulator")]
y = 560
for i, (t, s) in enumerate(items):
    col = i % 2
    x0 = 140 + col * 1380
    yy = y + (i // 2) * 470
    d.rounded_rectangle((x0, yy, x0 + 1320, yy + 410), 30, fill=WHITE, outline="#D9DEE4", width=2)
    d.rectangle((x0, yy, x0 + 1320, yy + 14), fill=TEAL if i < 4 else AMBER)
    d.text((x0 + 60, yy + 80), t, font=f(60, "Bold"), fill=INK)
    d.multiline_text((x0 + 60, yy + 190), s, font=f(38, "Regular"), fill=MUTED, spacing=12)
footnote(d, text="Requires Microsoft Excel (2010 or later, Windows/Mac) or a free Google account. No macros, add-ins or subscriptions.")
save(c, "09_whats_included_3000x2250.jpg")

# GUMROAD -------------------------------------------------------------------------------------------
c, d = base(1280, 720)
d.text((60, 52), "NoviraNest", font=f(22, "Bold"), fill=TEAL)
d.text((60, 100), "Food Truck Profit &\nPricing System PRO", font=f(54, "Bold", True), fill=INK, spacing=6)
d.multiline_text((62, 260), "Menu pricing · Recipe costing · Events\nBreak-even · Scenarios · Inventory · P&L", font=f(24, "Regular"), fill=MUTED, spacing=10)
x = 60
for t in ("Excel + Google Sheets", "$ / £"):
    x = pill(d, (x, 380), t, size=20) + 14
window(c, shot("sample_01_Dashboard"), (640, 40, 1240, 690), "", radius=14)
save(c, "gumroad_cover_1280x720.jpg")

c, d = base(600, 600)
d.rectangle((0, 0, 600, 600), fill=INK)
d.rectangle((0, 0, 600, 10), fill=TEAL)
d.text((300, 120), "NoviraNest", font=f(30, "Bold"), fill="#5EEAD4", anchor="mm")
d.multiline_text((300, 270), "Food Truck\nProfit & Pricing\nPRO", font=f(58, "Bold", True), fill=WHITE, anchor="mm", align="center", spacing=8)
d.text((300, 470), "Excel  ·  Google Sheets", font=f(26, "Medium"), fill="#C9D3DD", anchor="mm")
save(c, "gumroad_thumbnail_600x600.jpg")
