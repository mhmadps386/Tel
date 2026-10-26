"""Independent re-implementation of every business calculation, straight from the raw
sample data in src/sample_data.py. Used as the expected-value source by the QA suite.
Deliberately does NOT read any formula or value from the workbook."""
import datetime as dt
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sample_data as SD  # noqa: E402

CAT_TYPE = {n: t for n, t, _ in SD.EXPENSE_CATEGORIES}
OPEX_TYPES = ("Fixed", "Labor", "Event Fees", "Variable")


def ceil_step(x, step):
    if step <= 0:
        return round(x, 2)
    return math.ceil(round(x / step, 9)) * step


class Oracle:
    def __init__(self, data=None, labor_rate=SD.LABOR_RATE, target=SD.TARGET_MARGIN, food_target=SD.FOODCOST_TARGET,
                 round_step=SD.ROUND_STEP, count_date=SD.COUNT_DATE):
        self.d = data or SD.build_dataset()
        self.labor_rate, self.target, self.food_target = labor_rate, target, food_target
        self.round_step, self.count_date = round_step, count_date
        self.inv = {i["name"]: i for i in self.d["inventory"]}

    # --- costing -------------------------------------------------------------
    def cpu(self, ing):
        i = self.inv[ing]
        return i["price"] / i["pack"]

    def to_su(self, ing, qty, unit):
        su = self.inv[ing]["unit"]
        d1, f1 = SD.UNIT[unit]
        d2, f2 = SD.UNIT[su]
        if d1 != d2:
            return None
        return qty * f1 / f2

    def recipe_ing_cost(self, item):
        return sum(self.to_su(n, q, u) * self.cpu(n) for n, q, u in SD.RECIPES.get(item, []))

    def menu(self):
        out = {}
        for name, cat, pk, mins, other, tm, price, _ in SD.MENU:
            ing = self.recipe_ing_cost(name)
            labor = mins / 60 * self.labor_rate
            total = ing + pk + labor + other
            t = tm if tm is not None else self.target
            sugg = ceil_step(total / (1 - t), self.round_step)
            profit = price - total
            margin = profit / price
            markup = profit / total
            food = ing / price
            if profit < 0:
                status = "LOSS"
            elif margin < t - 1e-5:
                status = "Below target"
            elif food > self.food_target:
                status = "High food cost"
            else:
                status = "Healthy"
            out[name] = dict(ing=ing, labor=labor, total=total, target=t, suggested=sugg, profit=profit,
                             margin=margin, markup=markup, food=food, status=status, price=price,
                             unit_cogs=ing + pk + other)
        return out

    # --- sales ----------------------------------------------------------------
    def sales_lines(self):
        m = self.menu()
        for s in self.d["sales"]:
            price = s["price"] if s["price"] is not None else m[s["item"]]["price"]
            rev = s["qty"] * price
            cogs = s["qty"] * m[s["item"]]["unit_cogs"]
            yield dict(s, rev=rev, cogs=cogs, gp=rev - cogs, ingc=s["qty"] * m[s["item"]]["ing"])

    def _lines(self):
        if not hasattr(self, "_cache"):
            self._cache = list(self.sales_lines())
        return self._cache

    def waste_lines(self):
        for w in self.d["waste"]:
            su = self.to_su(w["ing"], w["qty"], w["unit"])
            yield dict(w, su=su, value=su * self.cpu(w["ing"]))

    def period(self, start, end):
        p = defaultdict(float, {k: 0.0 for k in ("rev", "items", "cogs", "ing", "lines", "waste", "fixed", "labor",
                                                 "event", "var", "stock", "draw")})
        for s in self._lines():
            if start <= s["date"] <= end:
                p["rev"] += s["rev"]; p["items"] += s["qty"]; p["cogs"] += s["cogs"]; p["ing"] += s["ingc"]; p["lines"] += 1
        for w in self.waste_lines():
            if start <= w["date"] <= end:
                p["waste"] += w["value"]
        for e in self.d["expenses"]:
            if start <= e["date"] <= end:
                t = CAT_TYPE[e["cat"]]
                key = {"Fixed": "fixed", "Labor": "labor", "Event Fees": "event", "Variable": "var",
                       "Excluded - Stock Purchase": "stock", "Excluded - Owner Draw": "draw"}[t]
                p[key] += e["amt"]
        p["gp"] = p["rev"] - p["cogs"]
        p["opex"] = p["fixed"] + p["labor"] + p["event"] + p["var"]
        p["net"] = p["gp"] - p["waste"] - p["opex"]
        return dict(p)

    def month(self, y, m):
        start = dt.date(y, m, 1)
        end = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
        return self.period(start, end)

    def item_period(self, start, end):
        out = defaultdict(lambda: defaultdict(float))
        for s in self._lines():
            if start <= s["date"] <= end:
                o = out[s["item"]]
                o["units"] += s["qty"]; o["rev"] += s["rev"]; o["gp"] += s["gp"]
        return out

    # --- inventory --------------------------------------------------------------
    def inventory(self):
        used = defaultdict(float)
        for s in self.d["sales"]:
            if s["date"] >= self.count_date:
                for n, q, u in SD.RECIPES[s["item"]]:
                    used[n] += self.to_su(n, q, u) * s["qty"]
        wasted = defaultdict(float)
        for w in self.waste_lines():
            if w["date"] >= self.count_date:
                wasted[w["ing"]] += w["su"]
        out = {}
        for name, i in self.inv.items():
            on = i["opening"] + i["purchased"] - used[name] - i["other"] - wasted[name]
            status = "Recount (negative)" if on < 0 else ("Reorder" if on <= i["reorder"] else "OK")
            out[name] = dict(used=used[name], wasted=wasted[name], on_hand=on, value=max(0, on) * self.cpu(name),
                             status=status, waste_value=wasted[name] * self.cpu(name))
        return out

    # --- break-even ---------------------------------------------------------------
    def breakeven(self, year=SD.YEAR):
        y = self.period(dt.date(year, 1, 1), dt.date(year, 12, 31))
        price = y["rev"] / y["items"]
        vc = y["cogs"] / y["items"]
        pct = SD.OTHER_VARIABLE_PCT
        fixed = sum(v for _, v in SD.BREAK_EVEN_BUDGET)
        cm = price - vc - price * pct
        be_items = math.ceil(fixed / cm)
        be_rev = fixed / (cm / price)
        tgt_items = math.ceil((fixed + SD.TARGET_PROFIT) / cm)
        months_items = [self.month(year, m)["items"] for m in range(1, 13)]
        active = [x for x in months_items if x > 0]
        avg_items = sum(active) / len(active)
        return dict(price=price, vc=vc, cm=cm, cm_ratio=cm / price, fixed=fixed, be_items=be_items, be_rev=be_rev,
                    be_day=math.ceil(be_items / SD.SERVICE_DAYS), tgt_items=tgt_items,
                    tgt_rev=(fixed + SD.TARGET_PROFIT) / (cm / price), avg_items=avg_items,
                    safety=(avg_items - be_items) / avg_items)

    # --- event ---------------------------------------------------------------------
    def event(self):
        e = SD.EVENT
        res = []
        fixed = e["fee"] + e["staff"] * e["hours"] * e["wage"] + e["transport"] + e["fuel"] + e["other"]
        vpct = e["commission"] + e["card"] + e["food_pct"]
        for k in range(3):
            cust = round(e["attendance"][k] * e["buy_rate"][k])
            orders = round(cust * e["orders_per_customer"][k])
            rev = orders * e["aov"][k]
            profit = rev - rev * vpct - fixed
            be = math.ceil(fixed / (e["aov"][k] * (1 - vpct)))
            res.append(dict(customers=cust, orders=orders, revenue=rev, profit=profit, be_orders=be,
                            be_att=math.ceil(be / (e["buy_rate"][k] * e["orders_per_customer"][k]))))
        act = [s for s in self.sales_lines() if s["loc"] == e["name"]]
        a_rev = sum(s["rev"] for s in act)
        a_cogs = sum(s["cogs"] for s in act)
        a_fee = round(e["actual_fee"] + 0.026 * 8820.5, 2)
        a_profit = a_rev - a_cogs - a_fee - e["actual_staff"] - e["actual_other"]
        return dict(scen=res, fixed=fixed, a_rev=a_rev, a_items=sum(s["qty"] for s in act), a_cogs=a_cogs,
                    a_profit=a_profit, variance=a_profit - res[1]["profit"])

    # --- simulator -------------------------------------------------------------------
    def simulator(self, levers, year=SD.YEAR):
        y = self.period(dt.date(year, 1, 1), dt.date(year, 12, 31))
        n = sum(1 for m in range(1, 13) if self.month(year, m)["rev"] > 0)
        items = y["items"] / n
        price = y["rev"] / y["items"]
        ingc = y["ing"] / y["items"]
        pack = (y["cogs"] - y["ing"]) / y["items"]
        wages, fees, other, waste = y["labor"] / n, y["event"] / n, (y["fixed"] + y["var"]) / n, y["waste"] / n
        ing, vol, pr, lab, fee = levers

        def pnl(items, price, ingc, wages, fees, waste):
            rev = items * price
            gp = rev - items * ingc - items * pack
            fixed = wages + fees + other + waste
            return dict(rev=rev, gp=gp, net=gp - fixed, fixed=fixed, vc=ingc + pack)

        base = pnl(items, price, ingc, wages, fees, waste)
        sc = pnl(items * (1 + vol), price * (1 + pr), ingc * (1 + ing), wages * (1 + lab), fees * (1 + fee), waste * (1 + ing))
        need = (base["net"] + sc["fixed"]) / (items * (1 + vol)) + sc["vc"]
        return dict(base=base, scen=sc, price_needed=need, months=n)
