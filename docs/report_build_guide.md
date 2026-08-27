# Report Build Guide — SOP-Consensus

**All three pages are generated programmatically** by `scripts/build_report_page.py`,
which writes every visual straight into `pbip/SOP-Consensus.Report/report.json`.
Run it with Power BI Desktop closed, then reopen the `.pbip`:

```bash
python scripts/build_report_page.py
```

This doc documents what the script builds and doubles as the spec if you want
to rearrange a page by hand. All measures already exist in the model (display
folders: Demand, Supply, Inventory, Financial).

## Design language (all three pages)

- White visual cards (hidden border) on a `#F9F9F7` page canvas, set via
  per-visual `vcObjects.background`/`border` and each page's own
  `config.objects.background` — see `vc_chrome()` in the build script.
  **Do not use a custom report theme** (resourcePackages + visualStyles
  registration) — it silently broke every card/chart/table render with no
  usable error in this Desktop version; see the memory note.
- Semantic series colors, fixed: demand/consensus/truth **blue `#2A78D6`**
  (or **ink `#0B0B0B`** for an actual/ground-truth line), capacity/neutral
  reference **ink `#52514E`**, constrained/loaded/pressured supply **orange
  `#EC835A`**, any forecast-or-plan (not-yet-real) line **dashed**. Status
  colors only for state: critical `#D03B3B`, serious `#EC835A` — never as
  series colors.
- One shared axis per combo chart (no dual axes, via `valueAxis.secShow:
  false`); titles written as takeaways, not labels ("Consensus demand
  exceeds capacity Oct–Dec 2026").
- Table conditional-formatting gradients (`linearGradient2` FillRule) also
  broke silently — don't reach for them; sort order (worst-first, via
  `data_table()`'s `sort_entity`/`sort_prop`) plus a text callout carries a
  comparative story just as well and is proven to render.
- **`data_table()` alias gotcha:** the function auto-assigns query aliases by
  first-seen entity order; pass `sort_entity`/`sort_prop` (not a raw alias
  string) so the OrderBy always resolves to the alias the function actually
  generated. A mismatched hardcoded alias here doesn't error — Power BI just
  silently drops the sort and falls back to alphabetical-by-first-column.
  (This shipped once and was caught by actually reading the rendered row
  order, not just checking the report loaded — always verify sort order
  visually after touching a table.)

Conventions: month axis = `Date[YearMonth]` (already sorted correctly via
`Date[Month]` sort on MonthName; YearMonth sorts alphabetically = chronologically).

---

## Page 1 — Consensus One-Pager

*The S&OP meeting page: one screen that holds demand, supply, inventory, and
money at once.*

### KPI band (5 cards)

Filtered to `Date[Year] = 2026` (Q4-26 utilization card also filters `Quarter = "Q4"`):

| Card | Field | Value |
|------|-------|-------|
| Consensus Revenue | `[Consensus Revenue]` | $506.2M |
| Gap to AOP | `[Gap to AOP]` | ($18.8M) |
| Q4-26 Capacity Utilization | `[Capacity Utilization %]` | 120.5% |
| Revenue at Risk | `[Revenue at Risk]` | $29.7M |
| Sales Forecast Bias | `[Forecast Bias %]` | +10.9% |

### Demand vs. capacity (combo chart)

Columns = `[Consensus Units]` (blue); lines = `[Capacity Units]` (ink) and
`[Constrained Units]` (orange). Single shared axis. Consensus punches through
capacity Oct–Dec 2026.

### Revenue vs. AOP (line chart)

`[Consensus Revenue]` solid blue vs. `[AOP Revenue]` dashed gray — the two
separate starting in July.

### Trade-off table + decision panel

Table: ProductName, MarginTier, `[Days of Supply]`, `[On Hand Units]`,
`[Gross Margin %]`, `[Forecast Accuracy %]`, sorted worst-days-of-supply-first,
filtered to `2026-08`. Four numbered decision callouts, colored by urgency
(critical red / serious orange).

---

## Page 2 — Demand Review

### Forecast versions vs. actuals (line chart, full width)

All months, no filter. Four series: `[Stat Forecast Units]` (dashed muted),
`[Sales Forecast Units]` (dashed orange), `[Consensus Units]` (solid blue),
`[Actual Units]` (solid ink, thickest). Dashed = not-yet-real; solid = actual
or committed consensus. The bias is a visible gap, not an asserted number.

### Bias trend (column chart)

`[Forecast Bias %]` by month, filtered `IsActual = 1`, single series orange.
Consistently positive ≈ +8–13%: systematic, not noise.

### Accuracy by SKU (horizontal bar chart)

`[Forecast Accuracy %]` by `Product[ProductName]`, filtered `IsActual = 1`,
sorted ascending (worst first), single series blue.

### Slicers (right rail)

Three stacked: `Date[Year]`, `Product[MarginTier]`, `Channel[ChannelName]`.

---

## Page 3 — Supply & Inventory

### Plant loading, Q4-26 (combo chart)

Category = `Location[LocationName]` (only the two plants — Supply has no DC
rows, so the categorical axis naturally excludes the DC members of the
Location dimension). Bars = `[Capacity Units]` (muted); line = `[Production
Plan Units]` (orange), summed over Q4. Single shared axis.

**Why not "utilization by plant"?** `[Capacity Utilization %]` divides
company-wide `[Consensus Units]` (from Demand, which has no plant relationship)
by plant-level `[Capacity Units]` — splitting it by plant would inflate both
plants' numbers identically off the same numerator, which is misleading, not
just a display nuance. `[Production Plan Units]`, by contrast, is genuinely
plant-scoped in the data (allocated proportionally to each plant's capacity
share at generation time), so plan-vs-capacity is the honest per-plant story.

### Projected inventory (line chart)

`[Projected Inventory Units]`, single series blue, 2026-01 → 2027-06. Line-total
only (production isn't tracked per SKU) — don't add a Product legend.

### SKU risk matrix (table, full width)

ProductName, MarginTier, `[Days of Supply]`, `[On Hand Units]`, `[Safety Stock
Units]`, `[Inventory Value]`, `[Gross Margin %]`, sorted worst-days-of-supply-
first, filtered to `2026-08`.

---

## Validation queries (DAX query view)

Paste into DAX query view to confirm the four tensions after any data regeneration:

```dax
// 1. Q4-26 utilization ≈ 120%
EVALUATE ROW("Util", CALCULATE([Capacity Utilization %], 'Date'[Year] = 2026, 'Date'[Quarter] = "Q4"))

// 2. Cumulative sales-forecast bias ≈ +10%
EVALUATE ROW("Bias", [Forecast Bias %])

// 3. DOS by SKU at Aug-26 (Melon > 90, Citrus near zero)
EVALUATE SUMMARIZECOLUMNS(Product[ProductName], TREATAS({"2026-08"}, 'Date'[YearMonth]), "DOS", [Days of Supply])

// 4. H2-26 gap to AOP ≈ -6%
EVALUATE ROW("Gap", CALCULATE([Gap to AOP %], 'Date'[Year] = 2026, 'Date'[Month] >= 7))
```
