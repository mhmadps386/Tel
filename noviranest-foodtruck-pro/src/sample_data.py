"""Deterministic, clearly FICTIONAL demo data for the sample workbook.

Nothing here represents a real business. Every number is generated from the
assumptions below so the QA suite can recompute expected results independently.
"""
import datetime as dt
import random

BUSINESS = "Copper Pan Street Kitchen (DEMO - fictional data)"
YEAR = 2026
LABOR_RATE = 16.00
TARGET_MARGIN = 0.62
FOODCOST_TARGET = 0.32
ROUND_STEP = 0.25
COUNT_DATE = dt.date(2026, 9, 1)

# Units: name -> (dimension, factor to base unit g / ml / each)
UNITS = [
    ("g", "Mass", 1), ("kg", "Mass", 1000), ("oz", "Mass", 28.349523125), ("lb", "Mass", 453.59237),
    ("ml", "Volume", 1), ("l", "Volume", 1000), ("tsp", "Volume", 4.92892159375),
    ("tbsp", "Volume", 14.78676478125), ("cup (US)", "Volume", 236.5882365),
    ("fl oz (US)", "Volume", 29.5735295625), ("fl oz (UK)", "Volume", 28.4130625),
    ("pint (US)", "Volume", 473.176473), ("pint (UK)", "Volume", 568.26125),
    ("gal (US)", "Volume", 3785.411784), ("gal (UK)", "Volume", 4546.09),
    ("each", "Count", 1), ("dozen", "Count", 12), ("portion", "Count", 1),
]
UNIT = {u: (d, f) for u, d, f in UNITS}

EXPENSE_CATEGORIES = [
    ("Commissary / Parking", "Fixed", "Kitchen rental, overnight parking"),
    ("Truck Loan / Lease", "Fixed", "Monthly truck or trailer payment"),
    ("Insurance", "Fixed", "Liability, vehicle, equipment"),
    ("Licenses & Permits", "Fixed", "Health permits, business licences"),
    ("POS / Software", "Fixed", "Point of sale, apps, subscriptions"),
    ("Phone & Internet", "Fixed", "Mobile data, hotspot"),
    ("Accounting & Legal", "Fixed", "Bookkeeper, accountant, legal"),
    ("Marketing & Advertising", "Fixed", "Social ads, printing, signage"),
    ("Staff Wages & Payroll", "Labor", "Wages incl. payroll taxes"),
    ("Event & Pitch Fees", "Event Fees", "Festival, market and pitch fees"),
    ("Fuel & Generator", "Variable", "Vehicle fuel, generator fuel"),
    ("Propane / Cooking Gas", "Variable", "Cooking gas refills"),
    ("Card Processing Fees", "Variable", "Card reader / payment fees"),
    ("Repairs & Maintenance", "Variable", "Truck and equipment repairs"),
    ("Cleaning & Disposables", "Variable", "Cleaning products, gloves"),
    ("Other Operating Expense", "Variable", "Anything else that runs the business"),
    ("Ingredient & Packaging Purchases", "Excluded - Stock Purchase", "Logged for cash records only; profit uses recipe COGS"),
    ("Owner's Draw", "Excluded - Owner Draw", "Money you pay yourself; not a business expense"),
]
COST_TYPES = ["Fixed", "Labor", "Event Fees", "Variable", "Excluded - Stock Purchase", "Excluded - Owner Draw"]
PAYMENT_METHODS = ["Card", "Cash", "Mobile Wallet", "Online / App", "Bank Transfer", "Invoice", "Other"]
MENU_CATEGORIES = ["Mains", "Sides", "Drinks", "Desserts", "Kids", "Specials", "Combos", "Catering"]
WASTE_REASONS = ["Expired", "Spoiled", "Over-prepped", "Dropped / Damaged", "Quality reject", "Staff error", "Other"]

# Ingredients: name, supplier, stock unit, pack size (stock units), pack price, reorder level
INGREDIENTS = [
    ("Ground beef 80/20", "Valley Meats", "lb", 10, 52.00, 12),
    ("Brioche buns", "Hearth Bakery", "each", 48, 28.80, 60),
    ("American cheese slices", "Valley Meats", "each", 160, 22.40, 80),
    ("Pork shoulder (cooked)", "Valley Meats", "lb", 20, 64.00, 8),
    ("Beef brisket (cooked)", "Valley Meats", "lb", 12, 78.00, 10),
    ("Corn tortillas", "Maria's Tortilleria", "each", 360, 21.60, 120),
    ("Chicken tenders", "Valley Meats", "kg", 10, 79.00, 6),
    ("Fries (frozen)", "Restaurant Depot", "lb", 30, 36.00, 25),
    ("Halloumi", "Restaurant Depot", "kg", 2.5, 42.50, 1.5),
    ("Flour tortillas 12in", "Maria's Tortilleria", "each", 72, 21.60, 24),
    ("Macaroni", "Restaurant Depot", "kg", 5, 11.50, 3),
    ("Cheddar (shredded)", "Restaurant Depot", "lb", 5, 22.50, 6),
    ("Whole milk", "Restaurant Depot", "gal (US)", 1, 4.20, 2),
    ("Lemons", "Green Farm Produce", "each", 100, 32.00, 60),
    ("Cane sugar", "Restaurant Depot", "kg", 10, 14.00, 3),
    ("Canned soda", "Restaurant Depot", "each", 24, 9.60, 48),
    ("Churro dough mix", "Restaurant Depot", "kg", 5, 18.50, 3),
    ("Cinnamon sugar", "Restaurant Depot", "kg", 1, 6.80, 0.5),
    ("Green cabbage", "Green Farm Produce", "kg", 10, 14.00, 4),
    ("Slaw dressing", "Restaurant Depot", "l", 4, 15.60, 2),
    ("BBQ sauce", "Restaurant Depot", "gal (US)", 1, 18.90, 1),
    ("House burger sauce", "Made in-house", "l", 2, 9.80, 1.5),
    ("Dill pickles", "Restaurant Depot", "kg", 3, 12.90, 1.5),
    ("Lettuce (heads)", "Green Farm Produce", "each", 24, 30.00, 8),
    ("Tomatoes", "Green Farm Produce", "kg", 5, 17.50, 3),
    ("Onions", "Green Farm Produce", "kg", 10, 12.00, 4),
    ("Frying oil", "Restaurant Depot", "l", 20, 46.00, 15),
    ("Pico de gallo", "Made in-house", "kg", 2, 13.00, 2),
    ("Cotija cheese", "Restaurant Depot", "lb", 2, 15.80, 1),
    ("Bacon", "Valley Meats", "lb", 15, 82.50, 5),
    ("Sour cream", "Restaurant Depot", "l", 2, 8.40, 1),
    ("Juice boxes", "Restaurant Depot", "each", 40, 18.00, 20),
]

# Menu: name, category, packaging, prep minutes, other variable, target margin (None=default), price, base daily qty
MENU = [
    ("Smash Burger", "Mains", 0.35, 3, 0.15, None, 11.00, 15),
    ("Double Smash Burger", "Mains", 0.35, 4, 0.15, None, 14.50, 8),
    ("Pulled Pork Sandwich", "Mains", 0.35, 2, 0.15, None, 12.00, 9),
    ("Brisket Tacos (3)", "Mains", 0.40, 4, 0.15, None, 11.50, 10),
    ("Chicken Tenders Basket", "Mains", 0.45, 4, 0.15, None, 13.00, 8),
    ("Loaded Fries", "Sides", 0.40, 3, 0.10, None, 10.00, 8),
    ("Halloumi Veggie Wrap", "Mains", 0.30, 3, 0.10, None, 11.50, 4),
    ("Mac & Cheese Bowl", "Sides", 0.35, 2, 0.10, None, 9.00, 6),
    ("Fresh Lemonade", "Drinks", 0.30, 1, 0.05, 0.75, 5.00, 12),
    ("Canned Soda", "Drinks", 0.00, 0, 0.05, 0.75, 2.50, 10),
    ("Churro Bites", "Desserts", 0.25, 2, 0.10, None, 6.00, 7),
    ("Side Slaw", "Sides", 0.25, 1, 0.05, None, 3.50, 4),
    ("Kids Slider Meal", "Kids", 0.50, 3, 0.15, None, 3.50, 3),
]

# Recipes: menu item -> list of (ingredient, qty, unit)
RECIPES = {
    "Smash Burger": [("Ground beef 80/20", 4, "oz"), ("Brioche buns", 1, "each"), ("American cheese slices", 1, "each"),
                     ("House burger sauce", 20, "ml"), ("Dill pickles", 15, "g"), ("Onions", 20, "g"), ("Lettuce (heads)", 0.05, "each")],
    "Double Smash Burger": [("Ground beef 80/20", 8, "oz"), ("Brioche buns", 1, "each"), ("American cheese slices", 2, "each"),
                            ("House burger sauce", 25, "ml"), ("Dill pickles", 15, "g"), ("Onions", 25, "g")],
    "Pulled Pork Sandwich": [("Pork shoulder (cooked)", 5, "oz"), ("Brioche buns", 1, "each"), ("Green cabbage", 40, "g"),
                             ("Slaw dressing", 1, "tbsp"), ("BBQ sauce", 1, "fl oz (US)")],
    "Brisket Tacos (3)": [("Beef brisket (cooked)", 5, "oz"), ("Corn tortillas", 3, "each"), ("Pico de gallo", 60, "g"),
                          ("Cotija cheese", 1, "oz"), ("BBQ sauce", 20, "ml")],
    "Chicken Tenders Basket": [("Chicken tenders", 200, "g"), ("Fries (frozen)", 6, "oz"), ("Frying oil", 30, "ml"),
                               ("House burger sauce", 30, "ml")],
    "Loaded Fries": [("Fries (frozen)", 10, "oz"), ("Cheddar (shredded)", 2, "oz"), ("Bacon", 1.5, "oz"),
                     ("Sour cream", 30, "ml"), ("Onions", 10, "g"), ("Frying oil", 25, "ml")],
    "Halloumi Veggie Wrap": [("Halloumi", 100, "g"), ("Flour tortillas 12in", 1, "each"), ("Lettuce (heads)", 0.1, "each"),
                             ("Tomatoes", 50, "g"), ("House burger sauce", 20, "ml")],
    "Mac & Cheese Bowl": [("Macaroni", 120, "g"), ("Cheddar (shredded)", 3, "oz"), ("Whole milk", 0.5, "cup (US)"), ("Bacon", 0.5, "oz")],
    "Fresh Lemonade": [("Lemons", 1.5, "each"), ("Cane sugar", 40, "g")],
    "Canned Soda": [("Canned soda", 1, "each")],
    "Churro Bites": [("Churro dough mix", 120, "g"), ("Cinnamon sugar", 15, "g"), ("Frying oil", 40, "ml")],
    "Side Slaw": [("Green cabbage", 120, "g"), ("Slaw dressing", 40, "ml")],
    "Kids Slider Meal": [("Ground beef 80/20", 3, "oz"), ("Brioche buns", 1, "each"), ("American cheese slices", 1, "each"),
                         ("Fries (frozen)", 4, "oz"), ("Juice boxes", 1, "each")],
}

SEASON = {1: 0.55, 2: 0.6, 3: 0.75, 4: 0.9, 5: 1.05, 6: 1.2, 7: 1.3, 8: 1.25, 9: 1.0}
FOOD_FEST = "Summer Food Fest 2026"
NIGHT_MARKET = "Riverside Night Market"

BREAK_EVEN_BUDGET = [
    ("Commissary / parking", 650), ("Truck loan or lease", 890), ("Insurance", 210),
    ("Licences & permits (monthly share)", 117), ("POS & software", 79), ("Phone & internet", 75),
    ("Accounting", 100), ("Marketing", 150), ("Staff wages (planned)", 7000),
    ("Fuel, propane & generator", 950), ("Repairs reserve", 150), ("Other", 100),
]
OTHER_VARIABLE_PCT = 0.02
SERVICE_DAYS = 21
TARGET_PROFIT = 3000

EVENT = {
    "name": FOOD_FEST, "date": dt.date(2026, 7, 18), "notes": "Two-day festival, 2 x 11h shifts, flat pitch fee",
    "attendance": (5000, 7000, 9000), "buy_rate": (0.04, 0.05, 0.06), "orders_per_customer": (1.0, 1.0, 1.0),
    "aov": (18.00, 21.00, 23.00),
    "fee": 450, "commission": 0.0, "card": 0.026, "food_pct": 0.30, "staff": 3, "hours": 22, "wage": 17.50,
    "transport": 60, "fuel": 120, "other": 80,
    "actual_fee": 450, "actual_staff": 1155, "actual_other": 275,
}

SCENARIO_PRESET = "Ingredient inflation +10%"


def _service_days():
    d = dt.date(YEAR, 1, 1)
    while d <= dt.date(YEAR, 9, 30):
        if d.weekday() in (2, 3, 4, 5, 6):  # Wed-Sun
            yield d
        d += dt.timedelta(days=1)


def generate_sales(rng):
    """One line per menu item per service day. Returns list of dicts."""
    rows = []
    pay = ["Card"] * 70 + ["Cash"] * 15 + ["Mobile Wallet"] * 15
    for d in _service_days():
        loc = "Downtown Lunch Spot"
        mult = SEASON[d.month]
        if d.weekday() == 3:
            loc = "Brewery Thursday"
        if d.weekday() == 5 and d.month in (6, 7, 8):
            loc, mult = NIGHT_MARKET, mult * 1.5
        override = None
        if d in (dt.date(2026, 7, 18), dt.date(2026, 7, 19)):
            loc, mult, override = FOOD_FEST, mult * 2.6, 1.00
        for name, _cat, _pk, _pm, _ov, _tm, price, base in MENU:
            qty = max(0, round(rng.gauss(base * mult, base * mult * 0.18)))
            if qty == 0:
                continue
            rows.append({"date": d, "item": name, "qty": qty,
                         "price": (price + override) if override else None,
                         "pay": rng.choice(pay), "loc": loc})
    return rows


def generate_expenses(sales, unit_cost):
    exp = []

    def add(d, cat, desc, amt, pay="Bank Transfer", vendor=""):
        exp.append({"date": d, "cat": cat, "desc": desc, "amt": round(amt, 2), "pay": pay, "vendor": vendor})

    for m in range(1, 10):
        add(dt.date(YEAR, m, 1), "Commissary / Parking", "Monthly commissary rent", 650, vendor="Eastside Commissary")
        add(dt.date(YEAR, m, 3), "POS / Software", "POS subscription", 79, "Card", "POS provider")
        add(dt.date(YEAR, m, 5), "Truck Loan / Lease", "Truck loan payment", 890, vendor="Credit union")
        add(dt.date(YEAR, m, 10), "Insurance", "Liability & vehicle insurance", 210, vendor="Insurer")
        add(dt.date(YEAR, m, 15), "Phone & Internet", "Mobile + hotspot", 75, "Card", "Carrier")
        add(dt.date(YEAR, m, 20), "Marketing & Advertising", "Social media ads", 150, "Card", "Social ads")
        add(dt.date(YEAR, m, 25), "Cleaning & Disposables", "Cleaning supplies, gloves", 120, "Card", "Restaurant Depot")
        add(dt.date(YEAR, m, 28), "Owner's Draw", "Owner pay", 2500)
        card_rev = sum(r["qty"] * (r["price"] or menu_price(r["item"])) for r in sales
                       if r["date"].month == m and r["pay"] in ("Card", "Mobile Wallet"))
        last = (dt.date(YEAR, m + 1, 1) - dt.timedelta(days=1)) if m < 12 else dt.date(YEAR, 12, 31)
        add(last, "Card Processing Fees", "Card & wallet fees (2.6%)", card_rev * 0.026, vendor="Payment processor")
        if m in (1, 4, 7):
            add(dt.date(YEAR, m, 12), "Accounting & Legal", "Quarterly bookkeeping", 300, vendor="Bookkeeper")
    add(dt.date(YEAR, 1, 14), "Other Operating Expense", "Fire extinguisher inspection", 40, "Card")
    add(dt.date(YEAR, 3, 2), "Licenses & Permits", "Annual health permit renewal", 1150, vendor="County")
    add(dt.date(YEAR, 6, 4), "Licenses & Permits", "Health inspection fee", 250, vendor="County")
    add(dt.date(YEAR, 4, 12), "Repairs & Maintenance", "Generator service", 420, "Card", "Generator shop")
    add(dt.date(YEAR, 8, 8), "Repairs & Maintenance", "Fridge seal replacement", 260, "Card", "Refrigeration tech")
    add(dt.date(YEAR, 6, 15), "Event & Pitch Fees", "Summer Food Fest pitch fee", 450, vendor="Festival organiser")

    days = sorted({r["date"] for r in sales})
    loc_by_day = {r["date"]: r["loc"] for r in sales}
    # weekly: wages, fuel, stock purchases (Mondays covering previous Wed-Sun)
    week = {}
    for d in days:
        monday = d + dt.timedelta(days=(7 - d.weekday()) % 7 or 7)
        week.setdefault(monday, []).append(d)
    for i, (monday, ds) in enumerate(sorted(week.items())):
        monday = ds[-1]  # book on the last service day of the week (keeps costs in the month they were incurred)
        hours = 0
        for d in ds:
            staff = 3 if (SEASON[d.month] >= 1.2 or loc_by_day[d] != "Downtown Lunch Spot") else 2
            hours += staff * 9
        add(monday, "Staff Wages & Payroll", f"Payroll week ending {ds[-1]:%d %b}", hours * 17.50, vendor="Payroll")
        add(monday, "Fuel & Generator", "Fuel & generator", 38 * len(ds), "Card", "Gas station")
        cogs = sum(r["qty"] * unit_cost[r["item"]] for r in sales if r["date"] in ds)
        add(monday, "Ingredient & Packaging Purchases", "Weekly stock order", cogs * 1.04, "Card", "Restaurant Depot")
        if i % 2 == 0:
            add(monday, "Propane / Cooking Gas", "Propane refill", 65, "Card", "Propane supplier")
    for d in days:
        if loc_by_day[d] == NIGHT_MARKET:
            add(d, "Event & Pitch Fees", "Night market pitch", 75, "Card", "Market organiser")
    exp.sort(key=lambda e: e["date"])
    return exp


def generate_waste(rng):
    items = [("Brioche buns", "each", (2, 8), "Expired"), ("Lettuce (heads)", "each", (1, 2), "Spoiled"),
             ("Fries (frozen)", "lb", (1, 3), "Over-prepped"), ("Tomatoes", "g", (300, 900), "Spoiled"),
             ("Lemons", "each", (3, 10), "Spoiled"), ("Ground beef 80/20", "oz", (8, 24), "Quality reject"),
             ("Pico de gallo", "g", (200, 600), "Over-prepped"), ("Chicken tenders", "g", (200, 800), "Dropped / Damaged"),
             ("Slaw dressing", "ml", (100, 400), "Expired"), ("Churro dough mix", "g", (150, 400), "Over-prepped")]
    out = []
    for m in range(1, 10):
        for k in range(5):
            name, unit, (lo, hi), reason = items[(m * 3 + k) % len(items)]
            day = min(28, 3 + k * 5 + rng.randint(0, 3))
            qty = rng.randint(lo, hi) * 6
            out.append({"date": dt.date(YEAR, m, day), "ing": name, "qty": qty, "unit": unit, "reason": reason})
    return sorted(out, key=lambda w: w["date"])


def menu_price(item):
    return next(m[6] for m in MENU if m[0] == item)


def ing_cost_per_unit(name):
    i = next(x for x in INGREDIENTS if x[0] == name)
    return i[4] / i[3]


def to_stock_units(name, qty, unit):
    su = next(x for x in INGREDIENTS if x[0] == name)[2]
    return qty * UNIT[unit][1] / UNIT[su][1]


def recipe_cost(item):
    return sum(to_stock_units(n, q, u) * ing_cost_per_unit(n) for n, q, u in RECIPES.get(item, []))


def unit_cogs():
    return {m[0]: recipe_cost(m[0]) + m[2] + m[4] for m in MENU}


def build_dataset(seed=20260101):
    rng = random.Random(seed)
    sales = generate_sales(rng)
    expenses = generate_expenses(sales, unit_cogs())
    waste = generate_waste(rng)
    # Inventory opening/purchases since count date sized from September usage
    usage = {i[0]: 0.0 for i in INGREDIENTS}
    for r in sales:
        if r["date"] >= COUNT_DATE:
            for n, q, u in RECIPES[r["item"]]:
                usage[n] += to_stock_units(n, q, u) * r["qty"]
    waste_su = {i[0]: 0.0 for i in INGREDIENTS}
    for w in waste:
        if w["date"] >= COUNT_DATE:
            waste_su[w["ing"]] += to_stock_units(w["ing"], w["qty"], w["unit"])
    low = {"Brioche buns", "Lemons", "Beef brisket (cooked)"}
    inventory = []
    for name, sup, su, pack, price, reorder in INGREDIENTS:
        need = usage[name] + waste_su[name]
        opening = round(max(reorder, need * 0.35), 1 if su != "each" else 0)
        if name in low:
            purchased = max(0, round((need - opening + reorder * 0.5) / pack) * pack)
        else:
            purchased = max(0, round((need - opening + reorder * 2.2) / pack + 0.5) * pack)
        inventory.append({"name": name, "supplier": sup, "unit": su, "pack": pack, "price": price,
                          "opening": opening, "purchased": purchased, "other": 0, "reorder": reorder})
    return {"sales": sales, "expenses": expenses, "waste": waste, "inventory": inventory}
