"""Builds probe.csv: the riskiest formula patterns used by the workbook, evaluated by Google Sheets
(upload as CSV -> Google converts and calculates) and by LibreOffice, then compared."""
import csv

data = [  # Date, Item, Qty, Status, Value
    ("2026-03-01", "Burger", 10, "OK", 100), ("2026-03-15", "Fries", 5, "OK", 25),
    ("2026-03-20", "Burger", 3, "Bad date", 30), ("2026-04-02", "Soda", 7, "OK", 14),
    ("2026-04-03", "Burger", 2, "OK", 20), ("2026-04-04", "Fries", 1, "Qty must be above 0", 0),
    ("2026-05-01", "Burger", 4, "OK", 35), ("", "", "", "", ""),
]
mixed = ["40", "", "72", "x", "", "", "", ""]
act = [(5, 0, "2026-01-01"), (0, 0, "2026-02-01"), (0, 3, "2026-03-01")]
units = [("g", 1), ("oz", 28.349523125), ("lb", 453.59237)]
tests = [
    ("T01 SUMIFS date range", '=SUMIFS(E2:E9,A2:A9,">="&DATE(2026,3,1),A2:A9,"<="&EOMONTH(DATE(2026,3,1),0),D2:D9,"OK")'),
    ("T02 SUMPRODUCT blank-safe count", '=SUMPRODUCT((D2:D12<>"")*(D2:D12<>"OK"))'),
    ("T03 N() on blank/text", '=N(F2)+N(B2)+N(5)'),
    ("T04 INDEX MATCH", '=INDEX(B2:B9,MATCH(14,E2:E9,0))'),
    ("T05 IFERROR lookup missing", '=IFERROR(INDEX(B2:B9,MATCH("Taco",B2:B9,0))&"","?")'),
    ("T06 LARGE tie-break key", '=INDEX(B2:B9,MATCH(LARGE(K2:K9,1),K2:K9,0))'),
    ("T07 CEILING step", '=CEILING(3.5/(1-0.62),0.25)'),
    ("T08 TEXT money half-up", '="$"&TEXT(ABS(-190589.5),"#,##0")'),
    ("T09 TEXT month", '=TEXT(DATE(2026,7,1),"mmm")'),
    ("T10 REPT bar", '=REPT("█",MIN(10,ROUND(0.6*10,0)))&REPT("░",MAX(0,10-ROUND(0.6*10,0)))'),
    ("T11 COUNTIF >0", '=COUNTIF(E2:E9,">0")'),
    ("T12 ISNA MATCH", '=ISNA(MATCH("Taco",B2:B9,0))'),
    ("T13 SUMIFS ignores text", '=SUMIFS(L2:L9,B2:B9,"Burger")'),
    ("T14 SUMPRODUCT activity", '=SUMPRODUCT(((M2:M4>0)+(N2:N4>0)>0)*(O2:O4>=DATE(2026,2,1)))'),
    ("T15 AVERAGEIF", '=AVERAGEIF(E2:E9,">0")'),
    ("T16 ROUNDUP break-even", '=ROUNDUP(10471/6.66,0)'),
    ("T17 nested IF on blank", '=IF(N(E9)<=0,"Set a price",IF(E9<0,"LOSS","Healthy"))'),
    ("T18 SEARCH", '=ISNUMBER(SEARCH("DEMO","Shop (DEMO - fictional)"))'),
    ("T19 COUNTIFS 3 criteria", '=COUNTIFS(A2:A9,">="&DATE(2026,3,1),A2:A9,"<="&DATE(2026,3,31),D2:D9,"OK")'),
    ("T20 date serial diff", '=DATE(2026,3,1)-DATE(2000,1,1)'),
    ("T21 TEXT percent", '=TEXT(0.6237,"0.0%")'),
    ("T22 unit conversion", '=150*INDEX(R2:R4,MATCH("oz",Q2:Q4,0))/INDEX(R2:R4,MATCH("lb",Q2:Q4,0))'),
    ("T23 SUMIFS item+date+status", '=SUMIFS(C2:C9,B2:B9,"Burger",A2:A9,">="&DATE(2026,3,1),D2:D9,"OK")'),
    ("T24 TEXT negative sign", '=IF(-41<0,"-","")&"£"&TEXT(ABS(-41.4),"#,##0")'),
    ("T25 Excel ROUND half", '=ROUND(2.675,2)'),
]
rows = [["Date", "Item", "Qty", "Status", "Value", "Blank", "", "Test", "Result", "", "Key", "Mixed", "Rev", "Opex", "Month", "", "Unit", "Factor"]]
n = max(len(data), len(tests))
for i in range(n):
    r = i + 2
    d = list(data[i]) if i < len(data) else [""] * 5
    row = d + ["", ""]
    row += [tests[i][0], tests[i][1], ""] if i < len(tests) else ["", "", ""]
    row += [f'=IF(B{r}="",-1,N(C{r})+ROW()/1000000)' if i < len(data) else "", mixed[i] if i < len(mixed) else ""]
    row += list(act[i]) if i < len(act) else ["", "", ""]
    row += [""] + (list(units[i]) if i < len(units) else ["", ""])
    rows.append(row)
with open("probe.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)
print(len(rows), "rows")
