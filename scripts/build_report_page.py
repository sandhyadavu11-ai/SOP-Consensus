"""Builds all three pages of pbip/SOP-Consensus.Report/report.json:
  Page 1 — Consensus One-Pager (demand/supply/inventory/financial reconciled)
  Page 2 — Demand Review (forecast versions, bias trend, accuracy by SKU)
  Page 3 — Supply & Inventory (plant loading, projected inventory, risk matrix)

Executive-styled throughout: white visual cards (hidden border) on a soft
cream canvas, semantic series/status colors, single shared axis per chart,
chart titles written as takeaways. A hand-authored custom report theme
(resourcePackages + visualStyles) and a table conditional-formatting
gradient (linearGradient2 FillRule) were both tried on page 1 and both
silently broke visual rendering in Power BI Desktop with no useful error —
see the memory note on this. Every style below instead uses only
per-visual `objects`/`vcObjects` properties, verified against a live
reload.

Run with Power BI Desktop closed, then reopen the .pbip:
    python scripts/build_report_page.py
"""

import json
from pathlib import Path

REPORT = Path(__file__).resolve().parent.parent / "pbip" / "SOP-Consensus.Report" / "report.json"

# ---------------------------------------------------------------- palette
INK = "#0B0B0B"          # primary text
INK2 = "#52514E"         # secondary text / capacity reference
MUTED = "#898781"        # axis labels / forecast reference lines
CRITICAL = "#D03B3B"     # gap, revenue at risk
SERIOUS = "#EC835A"      # utilization, bias, constrained/loaded supply
BLUE = "#2A78D6"         # demand / consensus / truth (categorical slot 1)
WHITE = "#FFFFFF"
PAGE_BG = "#F9F9F7"       # canvas plane behind the white visual cards

MARGIN, GUTTER = 16, 12

_name_counter = 0
def vname():
    global _name_counter
    _name_counter += 1
    return f"consensusVisual{_name_counter:02d}"


def literal(value):
    if isinstance(value, bool):
        return {"Literal": {"Value": "true" if value else "false"}}
    if isinstance(value, int):
        return {"Literal": {"Value": f"{value}L"}}
    if isinstance(value, float):
        return {"Literal": {"Value": f"{value}D"}}
    return {"Literal": {"Value": "'" + str(value).replace("'", "''") + "'"}}


def literal_expr(value):
    return {"expr": literal(value)}


def color_expr(hexcolor):
    return {"solid": {"color": {"expr": literal(hexcolor)}}}


def measure_select(alias, entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop},
            "Name": f"{entity}.{prop}"}


def column_select(alias, entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop},
            "Name": f"{entity}.{prop}"}


def proto_query(froms, selects, order_by=None):
    q = {"Version": 2,
         "From": [{"Name": a, "Entity": e, "Type": 0} for a, e in froms],
         "Select": selects}
    if order_by:
        q["OrderBy"] = order_by
    return q


def in_filter(entity, prop, values):
    return {
        "name": f"Filter_{entity}_{prop}",
        "expression": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
        "filter": {"Version": 2,
                   "From": [{"Name": "f", "Entity": entity, "Type": 0}],
                   "Where": [{"Condition": {"In": {
                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": prop}}],
                       "Values": [[literal(v)] for v in values]}}}]},
        "type": "Categorical",
        "howCreated": 1,
    }


def container(x, y, w, h, z, visual_config, filters=None):
    cfg = dict(visual_config)
    cfg["name"] = vname()
    cfg["layouts"] = [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h}}]
    return {"x": float(x), "y": float(y), "z": float(z),
            "width": float(w), "height": float(h),
            "config": json.dumps(cfg),
            "filters": json.dumps(filters or [])}


def vc_chrome(title_text, title_size=None, title_color=None):
    """Visual-container chrome: white card, hidden border, styled title.
    Verified stable (unlike the theme-driven equivalent)."""
    props = {"show": literal_expr(True), "text": literal_expr(title_text)}
    if title_size:
        props["fontSize"] = literal_expr(float(title_size))
    if title_color:
        props["fontColor"] = color_expr(title_color)
    return {
        "title": [{"properties": props}],
        "background": [{"properties": {"color": color_expr(WHITE), "transparency": literal_expr(0)}}],
        "border": [{"properties": {"show": literal_expr(False)}}],
    }


def kpi_card(measure_entity, measure_name, title, value_color, millions=False):
    labels = {"color": color_expr(value_color), "fontSize": literal_expr(26)}
    if millions:
        labels["labelDisplayUnits"] = literal_expr(1000000.0)
        labels["labelPrecision"] = literal_expr(1)
    else:
        labels["labelDisplayUnits"] = literal_expr(0.0)
    return {
        "singleVisual": {
            "visualType": "card",
            "projections": {"Values": [{"queryRef": f"{measure_entity}.{measure_name}"}]},
            "prototypeQuery": proto_query(
                [("a", measure_entity)],
                [measure_select("a", measure_entity, measure_name)]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "labels": [{"properties": labels}],
                "categoryLabels": [{"properties": {"show": literal_expr(False)}}],
            },
            "vcObjects": vc_chrome(title, title_size=9, title_color=INK2),
        }
    }


def textbox(paragraphs, no_shadow=False):
    cfg = {
        "singleVisual": {
            "visualType": "textbox",
            "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
        }
    }
    if no_shadow:
        cfg["singleVisual"]["vcObjects"] = {
            "background": [{"properties": {"show": literal_expr(False)}}],
        }
    else:
        cfg["singleVisual"]["vcObjects"] = {
            "background": [{"properties": {"color": color_expr(WHITE), "transparency": literal_expr(0)}}],
            "border": [{"properties": {"show": literal_expr(False)}}],
        }
    return cfg


def run(text, bold=False, size=None, color=None):
    style = {}
    if bold:
        style["fontWeight"] = "bold"
    if size:
        style["fontSize"] = f"{size}pt"
    if color:
        style["color"] = color
    r = {"value": text}
    if style:
        r["textStyle"] = style
    return r


def series_fill(query_ref, hexcolor):
    return {"properties": {"fill": color_expr(hexcolor)},
            "selector": {"metadata": query_ref}}


def line_style(query_ref, width=None, dashed=False):
    props = {}
    if width:
        props["strokeWidth"] = literal_expr(float(width))
    if dashed:
        props["lineStyle"] = literal_expr("dashed")
    return {"properties": props, "selector": {"metadata": query_ref}}


def page_header(title_text, subtitle_text=None, width=1248):
    paras = [{"textRuns": [run(title_text, bold=True, size=16, color=INK)]}]
    if subtitle_text:
        paras.append({"textRuns": [run(subtitle_text, size=10, color=INK2)]})
    return container(MARGIN, 8, width, 36 if not subtitle_text else 44, 999,
                     textbox(paras, no_shadow=True))


def data_table(fields, filters, title, sort_entity, sort_prop, ascending=False):
    """Generic multi-field table: fields = [(entity, prop, 'column'|'measure'), ...].
    sort_entity/sort_prop must match one of the measure fields; the alias used
    in OrderBy is looked up from the same map used to build Select, so it can
    never drift out of sync (a hardcoded/mismatched alias here silently
    disables the sort — Power BI falls back to sorting by the first column
    with no error)."""
    aliases = {}
    for entity, _prop, _kind in fields:
        if entity not in aliases:
            aliases[entity] = chr(ord('a') + len(aliases))
    selects = []
    for entity, prop, kind in fields:
        fn = column_select if kind == "column" else measure_select
        selects.append(fn(aliases[entity], entity, prop))
    cfg = {
        "singleVisual": {
            "visualType": "tableEx",
            "projections": {"Values": [{"queryRef": f"{e}.{p}"} for e, p, _ in fields]},
            "prototypeQuery": proto_query(
                [(a, e) for e, a in aliases.items()], selects,
                order_by=[{"Direction": 1 if ascending else 2,
                           "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": aliases[sort_entity]}},
                                                      "Property": sort_prop}}}]),
            "drillFilterOtherVisuals": True,
            "vcObjects": vc_chrome(title),
        }
    }
    return cfg, filters


def slicer(entity, prop, title):
    return {
        "singleVisual": {
            "visualType": "slicer",
            "projections": {"Values": [{"queryRef": f"{entity}.{prop}"}]},
            "prototypeQuery": proto_query(
                [("a", entity)], [column_select("a", entity, prop)]),
            "drillFilterOtherVisuals": True,
            "vcObjects": vc_chrome(title, title_size=9, title_color=INK2),
        }
    }


# ================================================================== PAGE 1
def build_page1():
    KPI_W = (1280 - 2 * MARGIN - 4 * GUTTER) // 5          # 240
    LEFT_W, RIGHT_W = 756, 1280 - 2 * MARGIN - GUTTER - 756  # 756 / 480
    RIGHT_X = MARGIN + LEFT_W + GUTTER                       # 784

    Z = iter(range(1000, 1100))
    visuals = []

    visuals.append(container(MARGIN, 8, 900, 44, next(Z), textbox([
        {"textRuns": [run("Vitala S&OP Consensus — FY2026", bold=True, size=18, color=INK)]},
        {"textRuns": [run("Demand · supply · inventory · financial impact — one reconciled view",
                          size=10, color=INK2)]},
    ], no_shadow=True)))
    visuals.append(container(1280 - MARGIN - 330, 8, 330, 44, next(Z), textbox([
        {"horizontalTextAlignment": "right",
         "textRuns": [run("Actuals through Aug 2026", size=9, color=MUTED)]},
        {"horizontalTextAlignment": "right",
         "textRuns": [run("Plan year FY26 · Sept S&OP cycle", size=9, color=MUTED)]},
    ], no_shadow=True)))

    kpis = [
        ("AOP", "Consensus Revenue", "FY26 Consensus Revenue", INK, True, [in_filter("Date", "Year", [2026])]),
        ("AOP", "Gap to AOP", "FY26 Gap to AOP", CRITICAL, True, [in_filter("Date", "Year", [2026])]),
        ("Supply", "Capacity Utilization %", "Q4-26 Capacity Utilization", SERIOUS, False,
         [in_filter("Date", "Year", [2026]), in_filter("Date", "Quarter", ["Q4"])]),
        ("AOP", "Revenue at Risk", "FY26 Revenue at Risk", CRITICAL, True, [in_filter("Date", "Year", [2026])]),
        ("Demand", "Forecast Bias %", "Sales Forecast Bias", SERIOUS, False, None),
    ]
    x = MARGIN
    for entity, measure, title, vcolor, millions, filters in kpis:
        visuals.append(container(x, 60, KPI_W, 100, next(Z),
                                 kpi_card(entity, measure, title, vcolor, millions), filters))
        x += KPI_W + GUTTER

    combo = {
        "singleVisual": {
            "visualType": "lineClusteredColumnComboChart",
            "projections": {
                "Category": [{"queryRef": "Date.YearMonth"}],
                "Y": [{"queryRef": "Demand.Consensus Units"}],
                "Y2": [{"queryRef": "Supply.Capacity Units"},
                       {"queryRef": "AOP.Constrained Units"}],
            },
            "prototypeQuery": proto_query(
                [("d", "Date"), ("m", "Demand"), ("s", "Supply"), ("a", "AOP")],
                [column_select("d", "Date", "YearMonth"),
                 measure_select("m", "Demand", "Consensus Units"),
                 measure_select("s", "Supply", "Capacity Units"),
                 measure_select("a", "AOP", "Constrained Units")],
                order_by=[{"Direction": 1,
                           "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                     "Property": "YearMonth"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "valueAxis": [{"properties": {"secShow": literal_expr(False)}}],
                "dataPoint": [series_fill("Demand.Consensus Units", BLUE),
                              series_fill("Supply.Capacity Units", INK2),
                              series_fill("AOP.Constrained Units", SERIOUS)],
                "lineStyles": [line_style("Supply.Capacity Units", width=3),
                               line_style("AOP.Constrained Units", width=2)],
            },
            "vcObjects": vc_chrome("Consensus demand exceeds capacity Oct–Dec 2026 — pre-build or cap the promo"),
        }
    }
    visuals.append(container(MARGIN, 172, LEFT_W, 268, next(Z), combo,
                             [in_filter("Date", "Year", [2026, 2027])]))

    rev_line = {
        "singleVisual": {
            "visualType": "lineChart",
            "projections": {
                "Category": [{"queryRef": "Date.YearMonth"}],
                "Y": [{"queryRef": "AOP.Consensus Revenue"},
                      {"queryRef": "AOP.AOP Revenue"}],
            },
            "prototypeQuery": proto_query(
                [("d", "Date"), ("a", "AOP")],
                [column_select("d", "Date", "YearMonth"),
                 measure_select("a", "AOP", "Consensus Revenue"),
                 measure_select("a", "AOP", "AOP Revenue")],
                order_by=[{"Direction": 1,
                           "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                     "Property": "YearMonth"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "dataPoint": [series_fill("AOP.Consensus Revenue", BLUE),
                              series_fill("AOP.AOP Revenue", MUTED)],
                "lineStyles": [line_style("AOP.Consensus Revenue", width=3),
                               line_style("AOP.AOP Revenue", width=2, dashed=True)],
            },
            "vcObjects": vc_chrome("The H2 gap to plan opens in July — −6.0% vs. AOP"),
        }
    }
    visuals.append(container(RIGHT_X, 172, RIGHT_W, 268, next(Z), rev_line,
                             [in_filter("Date", "Year", [2026])]))

    table_fields = [
        ("Product", "ProductName", "column"),
        ("Product", "MarginTier", "column"),
        ("Inventory", "Days of Supply", "measure"),
        ("Inventory", "On Hand Units", "measure"),
        ("AOP", "Gross Margin %", "measure"),
        ("Demand", "Forecast Accuracy %", "measure"),
    ]
    table_cfg, table_filters = data_table(
        table_fields, [in_filter("Date", "YearMonth", ["2026-08"])],
        "The mix trade-off at Aug-26 — worst days-of-supply first",
        "Inventory", "Days of Supply", ascending=False)
    visuals.append(container(MARGIN, 452, LEFT_W, 252, next(Z), table_cfg, table_filters))

    def callout(n, lead, body, lead_color):
        return [{"textRuns": [run(f"{n}. {lead} — ", bold=True, size=10, color=lead_color),
                 run(body, size=10, color=INK2)]},
                {"textRuns": [run("", size=4)]}]

    paras = [{"textRuns": [run("Decisions on the table — Sept S&OP", bold=True, size=12, color=INK)]},
             {"textRuns": [run("", size=4)]}]
    paras += callout(1, "Pre-build or cap the promo",
                     "Q4 demand is 120% of capacity; the pre-build window closes in September.", CRITICAL)
    paras += callout(2, "Pick the planning number",
                     "Sales forecast runs +11% above actuals; planning supply on it ties up ~$2M/mo in working capital.", SERIOUS)
    paras += callout(3, "Shift line time to Citrus Boost",
                     "Melon Hydrate holds 133 days of supply at 18% margin while Citrus Boost 12pk (52% margin) is stocked out.", SERIOUS)
    paras += callout(4, "Close the H2 gap now",
                     "Consensus lands $18.8M under AOP; every lever is cheaper in May than in November.", CRITICAL)
    visuals.append(container(RIGHT_X, 452, RIGHT_W, 252, next(Z), textbox(paras)))

    return visuals


# ================================================================== PAGE 2
def build_page2():
    RAIL_W = 224
    MAIN_W = 1280 - 2 * MARGIN - GUTTER - RAIL_W             # 1012
    RAIL_X = MARGIN + MAIN_W + GUTTER                        # 1040

    Z = iter(range(2000, 2100))
    visuals = []

    visuals.append(page_header(
        "Demand Review — FY2026",
        "Forecast versions vs. actuals, bias trend, and accuracy by SKU"))

    forecast_versions = {
        "singleVisual": {
            "visualType": "lineChart",
            "projections": {
                "Category": [{"queryRef": "Date.YearMonth"}],
                "Y": [{"queryRef": "Demand.Stat Forecast Units"},
                      {"queryRef": "Demand.Sales Forecast Units"},
                      {"queryRef": "Demand.Consensus Units"},
                      {"queryRef": "Demand.Actual Units"}],
            },
            "prototypeQuery": proto_query(
                [("d", "Date"), ("m", "Demand")],
                [column_select("d", "Date", "YearMonth"),
                 measure_select("m", "Demand", "Stat Forecast Units"),
                 measure_select("m", "Demand", "Sales Forecast Units"),
                 measure_select("m", "Demand", "Consensus Units"),
                 measure_select("m", "Demand", "Actual Units")],
                order_by=[{"Direction": 1,
                           "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                     "Property": "YearMonth"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "dataPoint": [series_fill("Demand.Stat Forecast Units", MUTED),
                              series_fill("Demand.Sales Forecast Units", SERIOUS),
                              series_fill("Demand.Consensus Units", BLUE),
                              series_fill("Demand.Actual Units", INK)],
                "lineStyles": [line_style("Demand.Stat Forecast Units", width=2, dashed=True),
                               line_style("Demand.Sales Forecast Units", width=2, dashed=True),
                               line_style("Demand.Consensus Units", width=2),
                               line_style("Demand.Actual Units", width=3)],
            },
            "vcObjects": vc_chrome("Sales forecast runs above actuals every month — the bias is systematic, not noise"),
        }
    }
    visuals.append(container(MARGIN, 56, MAIN_W, 292, next(Z), forecast_versions))

    bias_trend = {
        "singleVisual": {
            "visualType": "clusteredColumnChart",
            "projections": {
                "Category": [{"queryRef": "Date.YearMonth"}],
                "Y": [{"queryRef": "Demand.Forecast Bias %"}],
            },
            "prototypeQuery": proto_query(
                [("d", "Date"), ("m", "Demand")],
                [column_select("d", "Date", "YearMonth"),
                 measure_select("m", "Demand", "Forecast Bias %")],
                order_by=[{"Direction": 1,
                           "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                     "Property": "YearMonth"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "dataPoint": [series_fill("Demand.Forecast Bias %", SERIOUS)],
            },
            "vcObjects": vc_chrome("Bias by month — consistently positive, +8% to +13%"),
        }
    }
    visuals.append(container(MARGIN, 360, 500, 344, next(Z), bias_trend,
                             [in_filter("Date", "IsActual", [1])]))

    accuracy_by_sku = {
        "singleVisual": {
            "visualType": "clusteredBarChart",
            "projections": {
                "Category": [{"queryRef": "Product.ProductName"}],
                "Y": [{"queryRef": "Demand.Forecast Accuracy %"}],
            },
            "prototypeQuery": proto_query(
                [("p", "Product"), ("m", "Demand")],
                [column_select("p", "Product", "ProductName"),
                 measure_select("m", "Demand", "Forecast Accuracy %")],
                order_by=[{"Direction": 1,
                           "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}},
                                                      "Property": "Forecast Accuracy %"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "dataPoint": [series_fill("Demand.Forecast Accuracy %", BLUE)],
            },
            "vcObjects": vc_chrome("Accuracy by SKU — worst first"),
        }
    }
    visuals.append(container(528, 360, 500, 344, next(Z), accuracy_by_sku,
                             [in_filter("Date", "IsActual", [1])]))

    rail_h = (720 - 56 - MARGIN - 2 * GUTTER) // 3           # 208
    visuals.append(container(RAIL_X, 56, RAIL_W, rail_h, next(Z),
                             slicer("Date", "Year", "Year")))
    visuals.append(container(RAIL_X, 56 + rail_h + GUTTER, RAIL_W, rail_h, next(Z),
                             slicer("Product", "MarginTier", "Margin tier")))
    visuals.append(container(RAIL_X, 56 + 2 * (rail_h + GUTTER), RAIL_W, rail_h, next(Z),
                             slicer("Channel", "ChannelName", "Channel")))

    return visuals


# ================================================================== PAGE 3
def build_page3():
    LEFT_W, RIGHT_W = 608, 1280 - 2 * MARGIN - GUTTER - 608  # 608 / 628

    Z = iter(range(3000, 3100))
    visuals = []

    visuals.append(page_header(
        "Supply & Inventory — FY2026",
        "Plant loading, projected inventory drawdown, and the SKU risk matrix"))

    plant_loading = {
        "singleVisual": {
            "visualType": "lineClusteredColumnComboChart",
            "projections": {
                "Category": [{"queryRef": "Location.LocationName"}],
                "Y": [{"queryRef": "Supply.Capacity Units"}],
                "Y2": [{"queryRef": "Supply.Production Plan Units"}],
            },
            "prototypeQuery": proto_query(
                [("l", "Location"), ("s", "Supply")],
                [column_select("l", "Location", "LocationName"),
                 measure_select("s", "Supply", "Capacity Units"),
                 measure_select("s", "Supply", "Production Plan Units")],
                order_by=[{"Direction": 1,
                           "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "l"}},
                                                     "Property": "LocationName"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "valueAxis": [{"properties": {"secShow": literal_expr(False)}}],
                "dataPoint": [series_fill("Supply.Capacity Units", MUTED),
                              series_fill("Supply.Production Plan Units", SERIOUS)],
                "lineStyles": [line_style("Supply.Production Plan Units", width=3)],
            },
            "vcObjects": vc_chrome("Plant loading, Q4-26 — production plan (line) against rated capacity (bar)"),
        }
    }
    visuals.append(container(MARGIN, 56, LEFT_W, 300, next(Z), plant_loading,
                             [in_filter("Date", "Year", [2026]), in_filter("Date", "Quarter", ["Q4"])]))

    projected_inv = {
        "singleVisual": {
            "visualType": "lineChart",
            "projections": {
                "Category": [{"queryRef": "Date.YearMonth"}],
                "Y": [{"queryRef": "Inventory.Projected Inventory Units"}],
            },
            "prototypeQuery": proto_query(
                [("d", "Date"), ("i", "Inventory")],
                [column_select("d", "Date", "YearMonth"),
                 measure_select("i", "Inventory", "Projected Inventory Units")],
                order_by=[{"Direction": 1,
                           "Expression": {"Column": {"Expression": {"SourceRef": {"Source": "d"}},
                                                     "Property": "YearMonth"}}}]),
            "drillFilterOtherVisuals": True,
            "objects": {
                "dataPoint": [series_fill("Inventory.Projected Inventory Units", BLUE)],
                "lineStyles": [line_style("Inventory.Projected Inventory Units", width=3)],
            },
            "vcObjects": vc_chrome("Projected inventory drains through the Q4 promo"),
        }
    }
    visuals.append(container(MARGIN + LEFT_W + GUTTER, 56, RIGHT_W, 300, next(Z), projected_inv,
                             [in_filter("Date", "Year", [2026, 2027])]))

    risk_fields = [
        ("Product", "ProductName", "column"),
        ("Product", "MarginTier", "column"),
        ("Inventory", "Days of Supply", "measure"),
        ("Inventory", "On Hand Units", "measure"),
        ("Inventory", "Safety Stock Units", "measure"),
        ("Inventory", "Inventory Value", "measure"),
        ("AOP", "Gross Margin %", "measure"),
    ]
    risk_cfg, risk_filters = data_table(
        risk_fields, [in_filter("Date", "YearMonth", ["2026-08"])],
        "SKU risk matrix at Aug-26 — worst days-of-supply first",
        "Inventory", "Days of Supply", ascending=False)
    visuals.append(container(MARGIN, 368, 1248, 336, next(Z), risk_cfg, risk_filters))

    return visuals


# ---------------------------------------------------------------- write
doc = json.loads(REPORT.read_text(encoding="utf-8"))

# strip any leftover custom-theme registration from earlier experiments
packages = doc.get("resourcePackages", [])
doc["resourcePackages"] = [p for p in packages
                           if p["resourcePackage"]["name"] != "RegisteredResources"]
report_config = json.loads(doc["config"])
report_config.get("themeCollection", {}).pop("customTheme", None)
doc["config"] = json.dumps(report_config)

page_config = json.dumps({"objects": {"background": [{"properties": {
    "color": color_expr(PAGE_BG), "transparency": literal_expr(0)}}]}})

builders = {"ReportSection1": build_page1, "ReportSection2": build_page2, "ReportSection3": build_page3}
for section in doc["sections"]:
    build = builders.get(section["name"])
    if build is None:
        continue
    section["visualContainers"] = build()
    section["config"] = page_config
    print(f"Wrote {len(section['visualContainers'])} visuals to '{section['displayName']}'")

REPORT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
