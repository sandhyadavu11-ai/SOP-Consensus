"""Synthetic S&OP dataset for the Vitala functional-beverage product line.

One product line, 8 SKUs, 2 plants, 3 DCs, 3 channels, monthly grain
Jan 2024 - Jun 2027 (actuals through Aug 2026).

Four tensions are deliberately baked in so the consensus view has real
decisions to surface:
  1. Q4 2026 promo demand exceeds combined plant capacity by ~15%.
  2. Sales forecast carries a persistent +8-12% bias vs. stat forecast/actuals.
  3. V-MEL-24 (low margin) builds >90 days of supply while V-CIT-12
     (high margin) stocks out.
  4. H2 2026 consensus revenue lands ~6% under the AOP commitment.
"""

import csv
import math
import random
from datetime import date
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

START = date(2024, 1, 1)
END = date(2027, 6, 1)
LAST_ACTUAL = date(2026, 8, 1)  # last month with actuals


def month_range(start, end):
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(date(y, m, 1))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return months


MONTHS = month_range(START, END)

# ---------------------------------------------------------------- dimensions
SKUS = [
    # sku, name, pack, margin_tier, list_price, std_cost, base_demand, growth/yr
    ("V-CIT-12", "Citrus Boost 12pk", 12, "High", 28.00, 13.50, 200_000, 0.14),
    ("V-BER-12", "Berry Focus 12pk", 12, "High", 27.50, 13.80, 155_000, 0.09),
    ("V-TRO-12", "Tropical Calm 12pk", 12, "Mid", 24.00, 13.90, 115_000, 0.05),
    ("V-CIT-24", "Citrus Boost 24pk", 24, "Mid", 44.00, 26.50, 125_000, 0.07),
    ("V-BER-24", "Berry Focus 24pk", 24, "Mid", 43.00, 26.80, 105_000, 0.05),
    ("V-GIN-12", "Ginger Revive 12pk", 12, "Mid", 24.50, 14.20, 85_000, 0.04),
    ("V-MEL-24", "Melon Hydrate 24pk", 24, "Low", 33.00, 27.20, 135_000, -0.12),
    ("V-COC-24", "Coco Splash 24pk", 24, "Low", 34.00, 27.60, 95_000, 0.00),
]

CHANNELS = [("CH-RET", "Retail", 0.55), ("CH-CLB", "Club", 0.30), ("CH-ECM", "E-commerce", 0.15)]
PLANTS = [("PL-COL", "Columbus Plant", "Plant", 800_000), ("PL-REN", "Reno Plant", "Plant", 500_000)]
DCS = [("DC-EAST", "Eastern DC", 0.45), ("DC-CEN", "Central DC", 0.35), ("DC-WEST", "Western DC", 0.20)]

SEASONALITY = {1: 0.94, 2: 0.94, 3: 0.99, 4: 1.02, 5: 1.06, 6: 1.10,
               7: 1.12, 8: 1.08, 9: 1.01, 10: 0.97, 11: 0.96, 12: 1.03}

PROMO_MONTHS = {date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)}
PROMO_SKUS = {"V-CIT-12", "V-BER-12", "V-CIT-24", "V-BER-24"}
PROMO_UPLIFT = 1.45  # club/retail feature+display program

def years_since_start(d):
    return (d.year - START.year) + (d.month - START.month) / 12.0


# ------------------------------------------------------------- demand build
# stat forecast = clean underlying signal; sales forecast = stat * bias
# (plus promo, which sales correctly adds); consensus = stat + 60% of gap.
demand = {}  # (month, sku) -> dict
for sku, name, pack, tier, price, cost, base, growth in SKUS:
    for m in MONTHS:
        t = years_since_start(m)
        level = base * ((1 + growth) ** t) * SEASONALITY[m.month]
        stat = level * random.uniform(0.99, 1.01)
        bias = random.uniform(1.08, 1.12)
        sales = stat * bias
        promo = sku in PROMO_SKUS and m in PROMO_MONTHS
        if promo:
            # stat model doesn't know the promo; sales layers it on
            sales = stat * bias * PROMO_UPLIFT
            consensus = stat + 0.85 * (sales - stat)  # promo largely accepted
        else:
            consensus = stat + 0.60 * (sales - stat)
        # true unconstrained demand tracks stat, promo included
        true_demand = stat * random.uniform(0.97, 1.03) * (PROMO_UPLIFT * 0.92 if promo else 1.0)
        demand[(m, sku)] = {
            "stat": stat, "sales": sales, "consensus": consensus, "true": true_demand,
        }

# ------------------------------------------------------------ supply build
# Production plan follows consensus, except:
#   V-MEL-24 keeps running at 2024 batch levels (min run quantities) -> build
#   V-CIT-12 is under-allocated (line time given to MEL batches) -> stockouts
prod_plan = {}
for sku, name, pack, tier, price, cost, base, growth in SKUS:
    for m in MONTHS:
        c = demand[(m, sku)]["consensus"]
        if sku == "V-MEL-24":
            t = years_since_start(m)
            legacy = base * 0.90 * SEASONALITY[m.month]  # ignores the decline
            prod_plan[(m, sku)] = max(c, legacy)
        elif sku == "V-CIT-12":
            prod_plan[(m, sku)] = c * 0.88
        else:
            prod_plan[(m, sku)] = c * random.uniform(0.99, 1.01)

# -------------------------------------------------- inventory / shipments sim
inv = {sku: SKUS[i][6] * 1.2 for i, (sku, *_rest) in enumerate(SKUS)}
inv = {s[0]: s[6] * 1.2 for s in SKUS}
inventory_rows = []   # ending on-hand by month/sku (actuals only)
shipped = {}          # (month, sku) -> actual shipments
for m in MONTHS:
    if m > LAST_ACTUAL:
        break
    for s in SKUS:
        sku = s[0]
        d = demand[(m, sku)]
        production = prod_plan[(m, sku)] * random.uniform(0.97, 1.01)
        available = inv[sku] + production
        ship = min(d["true"], available)
        inv[sku] = max(0.0, available - ship)
        shipped[(m, sku)] = ship
        inventory_rows.append((m, sku, inv[sku], d["consensus"] * 0.5))

# ---------------------------------------------------------------- write csvs
def write_csv(fname, header, rows):
    path = DATA_DIR / fname
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"  {fname}: {len(rows):,} rows")


print("Writing CSVs to", DATA_DIR)

write_csv("dim_date.csv",
          ["Date", "Year", "Month", "MonthName", "Quarter", "YearMonth", "IsActual"],
          [[m.isoformat(), m.year, m.month, m.strftime("%b"),
            f"Q{(m.month - 1) // 3 + 1}", m.strftime("%Y-%m"),
            1 if m <= LAST_ACTUAL else 0] for m in MONTHS])

write_csv("dim_product.csv",
          ["SKU", "ProductName", "PackSize", "MarginTier", "ListPrice", "StdCost"],
          [[s[0], s[1], s[2], s[3], f"{s[4]:.2f}", f"{s[5]:.2f}"] for s in SKUS])

write_csv("dim_location.csv",
          ["LocationID", "LocationName", "LocationType"],
          [[p[0], p[1], p[2]] for p in PLANTS] + [[d[0], d[1], "DC"] for d in DCS])

write_csv("dim_channel.csv",
          ["ChannelID", "ChannelName"],
          [[c[0], c[1]] for c in CHANNELS])

demand_rows = []
for m in MONTHS:
    for s in SKUS:
        sku = s[0]
        d = demand[(m, sku)]
        for ch_id, _ch_name, share in CHANNELS:
            actual = ""
            if (m, sku) in shipped:
                actual = round(shipped[(m, sku)] * share)
            demand_rows.append([
                m.isoformat(), sku, ch_id,
                round(d["stat"] * share), round(d["sales"] * share),
                round(d["consensus"] * share), actual,
            ])
write_csv("fact_demand.csv",
          ["Date", "SKU", "ChannelID", "StatForecastUnits", "SalesForecastUnits",
           "ConsensusForecastUnits", "ActualUnits"],
          demand_rows)

supply_rows = []
for m in MONTHS:
    total_plan = sum(prod_plan[(m, s[0])] for s in SKUS)
    for pl_id, _pl_name, _t, cap in PLANTS:
        share = cap / sum(p[3] for p in PLANTS)
        capacity = cap * (0.92 if (pl_id == "PL-REN" and m.month == 3) else 1.0)  # annual maintenance
        plan = min(total_plan * share, capacity)
        actual = ""
        if m <= LAST_ACTUAL:
            actual = round(plan * random.uniform(0.96, 1.00))
        supply_rows.append([m.isoformat(), pl_id, round(capacity), round(plan), actual])
write_csv("fact_supply.csv",
          ["Date", "PlantID", "CapacityUnits", "ProductionPlanUnits", "ActualProductionUnits"],
          supply_rows)

inv_rows = []
for m, sku, on_hand, ss in inventory_rows:
    for dc_id, _dc, share in DCS:
        inv_rows.append([m.isoformat(), sku, dc_id, round(on_hand * share), round(ss * share)])
write_csv("fact_inventory.csv",
          ["Date", "SKU", "DCID", "OnHandUnits", "SafetyStockUnits"],
          inv_rows)

# AOP: committed in Nov 2025 assuming +12% growth and richer mix than
# what consensus now shows -> H2 2026 gap of about -6%.
aop_rows = []
for m in MONTHS:
    if m.year not in (2026, 2027):
        continue
    consensus_rev = sum(
        demand[(m, s[0])]["consensus"] * s[4] for s in SKUS
    )
    factor = 1.005 if (m.year == 2026 and m.month <= 6) else 1.064
    aop_rows.append([m.isoformat(), round(consensus_rev * factor)])
write_csv("fact_aop.csv", ["Date", "AOPRevenue"], aop_rows)

# ------------------------------------------------------------- validation
print("\n--- validation: the four tensions ---")

q4 = [date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)]
cons_q4 = sum(demand[(m, s[0])]["consensus"] for m in q4 for s in SKUS)
cap_q4 = sum(r for m in q4 for (_pid, _n, _t, c) in PLANTS for r in [c])
print(f"1. Q4-26 consensus vs capacity: {cons_q4 / cap_q4:.1%} utilization")

hist = [m for m in MONTHS if m <= LAST_ACTUAL]
bias_num = sum(demand[(m, s[0])]["sales"] for m in hist for s in SKUS)
bias_den = sum(shipped[(m, s[0])] for m in hist for s in SKUS)
print(f"2. Sales forecast vs actual shipments (cumulative): {bias_num / bias_den - 1:+.1%}")

aug = date(2026, 8, 1)
mel_inv = next(oh for (m, sku, oh, _ss) in inventory_rows if m == aug and sku == "V-MEL-24")
mel_dem = demand[(aug, "V-MEL-24")]["consensus"]
cit_fill = (sum(shipped[(m, "V-CIT-12")] for m in hist[-12:])
            / sum(demand[(m, "V-CIT-12")]["true"] for m in hist[-12:]))
print(f"3. V-MEL-24 days of supply (Aug-26): {mel_inv / mel_dem * 30:.0f} days | "
      f"V-CIT-12 12-mo fill rate: {cit_fill:.1%}")

h2 = [date(2026, mm, 1) for mm in range(7, 13)]
cons_rev_h2 = sum(demand[(m, s[0])]["consensus"] * s[4] for m in h2 for s in SKUS)
aop_h2 = sum(v for d, v in aop_rows if date.fromisoformat(d).year == 2026
             and date.fromisoformat(d).month >= 7)
print(f"4. H2-26 consensus revenue vs AOP: {cons_rev_h2 / aop_h2 - 1:+.1%}")
