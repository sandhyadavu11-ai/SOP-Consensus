# Semantic Model Reference — SOP-Consensus

Source of truth is the TMDL in `pbip/SOP-Consensus.SemanticModel/definition/`.
This document is the human-readable map.

## Star schema

**Dimensions**

| Table | Grain | Key | Notes |
|-------|-------|-----|-------|
| Date | month | `Date` | Marked as date table; `IsActual` = 1 through 2026-08; `MonthName` sorted by `Month` |
| Product | SKU (8) | `SKU` | `ListPrice`, `StdCost`, `MarginTier` carry the financial layer |
| Location | plant/DC (5) | `LocationID` | 2 plants (Supply) + 3 DCs (Inventory) share one dimension, split by `LocationType` |
| Channel | channel (3) | `ChannelID` | Retail / Club / E-commerce |

**Facts** (all monthly grain, imported from `data/*.csv`)

| Table | Grain | Measures live here |
|-------|-------|--------------------|
| Demand | SKU × channel × month | Demand folder — three forecast versions + actual shipments |
| Supply | plant × month | Supply folder — capacity, production plan/actual |
| Inventory | SKU × DC × month | Inventory folder — month-end on-hand snapshot + safety stock |
| AOP | month | Financial folder — the annual operating plan revenue commitment |

Relationships: each fact → Date on `Date`; Demand/Inventory → Product on `SKU`;
Demand → Channel; Supply → Location (plants); Inventory → Location (DCs).

## Measures (28)

### Demand
- **Consensus / Stat Forecast / Sales Forecast / Actual Units** — plain sums of the four version columns.
- **Forecast Bias %** — (sales forecast − actuals) / actuals, restricted to actual months via `KEEPFILTERS('Date'[IsActual] = 1)`. Validated: **+10.9%** cumulative.
- **Forecast Accuracy %** — 1 − MAPE of consensus vs. actuals at SKU × month grain. Validated: **93.1%** overall.

### Supply
- **Capacity / Production Plan / Actual Production Units** — sums.
- **Capacity Utilization %** — consensus units ÷ capacity units. Works at any date slice; Product filters don't reach Supply (no SKU on that fact). Validated: **120.5%** for Q4-2026.
- **Capacity Gap Units** — consensus − capacity.

### Inventory (snapshot semantics)
On-hand is a month-end snapshot, so `On Hand Units` / `Safety Stock Units` take the **last date in context**, never a sum across months.
- **Days of Supply** — on-hand ÷ (average monthly consensus ÷ 30.4). Validated: Melon Hydrate **133 days**, Citrus Boost 12pk **0** at 2026-08.
- **Projected Inventory Units** — last actual on-hand + cumulative (production plan − consensus) beyond the actuals boundary. **Line-total only** — production plan has no SKU grain, so don't slice this by Product. Validated: 2.46M units Aug-26 → **1.64M** Dec-26 (the Q4 drawdown).
- **Inventory Value** — on-hand × standard cost, summed over SKUs.

### Financial
- **Consensus Revenue / COGS, Actual Revenue** — units × `ListPrice`/`StdCost` via `RELATED`. Validated FY-2026 consensus revenue: **$506M**.
- **Gross Margin / %** — revenue − COGS.
- **AOP Revenue, Gap to AOP / %** — consensus vs. the plan commitment. Validated: **−6.0%** H2-2026, −$18.8M FY.
- **Constrained Units** — month-by-month `MIN(consensus, capacity)`.
- **Revenue at Risk / Margin at Risk** — per month, unfillable units (consensus − capacity, floored at 0) × blended revenue/margin per unit. Validated: **$29.7M** revenue at risk FY-2026.

## Rebuild notes

- Regenerate data: `python scripts/generate_data.py` (seeded; prints a validation block that must show all four tensions).
- The PBIP opens in Power BI Desktop (developer mode); first open needs one **Refresh**. CSV paths in the partitions are absolute — if the project moves, update the eight `File.Contents` paths in `definition/tables/*.tmdl`.
- Auto date/time is disabled at the model level (`__PBI_TimeIntelligenceEnabled = 0`); time intelligence uses the explicit Date table.
