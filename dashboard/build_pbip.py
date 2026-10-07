"""
Generates the Power BI project (PBIP) for the Threadline dashboard as plain text files:
  dashboard/powerbi/Threadline.pbip                 <- double-click to open in Power BI Desktop
  dashboard/powerbi/Threadline.SemanticModel/       <- data model (tables, relationships, DAX measures)
  dashboard/powerbi/Threadline.Report/              <- 5 report pages

Why generate it? A PBIP is text, so the whole dashboard is reviewable in git and reproducible.

Usage: python dashboard/build_pbip.py [--export-folder "C:\\path\\to\\dashboard\\exports\\"]
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402
from export_dashboard_data import EXPORTS  # noqa: E402

OUT = ROOT / "dashboard" / "powerbi"
NAME = "Threadline"
DEFAULT_FOLDER = r"C:\Users\kanwa\Documents\ecommerce-funnel-ltv\dashboard\exports" + "\\"
EXPORT_FOLDER = sys.argv[sys.argv.index("--export-folder") + 1] if "--export-folder" in sys.argv else DEFAULT_FOLDER

# Colour system (same validated palette as the notebooks)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2A78D6", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#4A3AA7", "#E34948")
INK, INK2, GREY, BG = "#0B0B0B", "#52514E", "#8A8984", "#F7F7F5"

# =============================================================================
# SEMANTIC MODEL
# =============================================================================
TYPE_MAP = {  # duckdb type -> (TMSL dataType, M type)
    "BIGINT": ("int64", "Int64.Type"), "INTEGER": ("int64", "Int64.Type"), "HUGEINT": ("int64", "Int64.Type"),
    "SMALLINT": ("int64", "Int64.Type"), "DOUBLE": ("double", "type number"), "FLOAT": ("double", "type number"),
    "VARCHAR": ("string", "type text"), "BOOLEAN": ("boolean", "type logical"),
    "DATE": ("dateTime", "type date"), "TIMESTAMP": ("dateTime", "type datetime"),
}


def col_types(sql: str):
    d = db.query(f"DESCRIBE {sql}")
    out = []
    for name, t in zip(d.column_name, d.column_type):
        t = "DOUBLE" if t.startswith("DECIMAL") else t
        out.append((name, *TYPE_MAP[t]))
    return out


def csv_table(name: str, measures=(), hidden=(), sort_by=None):
    cols = col_types(EXPORTS[name])
    types = ", ".join(f'{{"{c}", {m}}}' for c, _, m in cols)
    expr = [
        "let",
        f'    Source = Csv.Document(File.Contents(ExportFolder & "{name}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]
    columns = []
    for c, dt, _ in cols:
        col = {"name": c, "dataType": dt, "sourceColumn": c,
               "summarizeBy": "sum" if dt in ("double",) and not c.endswith("_id") else "none"}
        if dt == "dateTime":
            col["formatString"] = "yyyy-mm-dd"
        if c in hidden:
            col["isHidden"] = True
        if sort_by and c in sort_by:
            col["sortByColumn"] = sort_by[c]
        columns.append(col)
    return {"name": name, "columns": columns, "measures": list(measures),
            "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expr}}]}


def static_table(name, columns, rows, sort_by=None):
    """Small lookup table defined inline in Power Query (no file needed)."""
    m_types = {"string": "text", "int64": "Int64.Type"}
    type_sig = ", ".join(f"{c} = {m_types[t]}" for c, t in columns)
    lit = lambda v: f'"{v}"' if isinstance(v, str) else str(v)  # noqa: E731
    body = ", ".join("{" + ", ".join(lit(v) for v in r) + "}" for r in rows)
    expr = ["let", f"    Source = #table(type table [{type_sig}], {{{body}}})", "in", "    Source"]
    cols = []
    for c, t in columns:
        col = {"name": c, "dataType": t, "sourceColumn": c, "summarizeBy": "none"}
        if sort_by and c in sort_by:
            col["sortByColumn"] = sort_by[c]
        cols.append(col)
    return {"name": name, "columns": cols,
            "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expr}}]}


def M(name, expr, fmt, folder=None, desc=None):
    m = {"name": name, "expression": expr, "formatString": fmt}
    if folder:
        m["displayFolder"] = folder
    if desc:
        m["description"] = desc
    return m


INR, INR0, PCT, PCT1, NUM, RATIO = '"₹"#,0', '"₹"#,0', "0.0%", "0.0%", "#,0", '0.00"×"'
PAID = '{"Paid Search", "Paid Social", "Affiliate"}'

orders_measures = [
    M("Net Revenue", "SUM(fct_orders[net_revenue])", INR, "Revenue",
      "Item revenue after discounts minus returns; excludes cancelled/RTO orders and shipping."),
    M("Gross Revenue", "SUM(fct_orders[gross_revenue])", INR, "Revenue"),
    M("Gross Margin", "SUM(fct_orders[gross_margin])", INR, "Revenue", "Net revenue minus cost of goods kept."),
    M("Gross Margin %", "DIVIDE([Gross Margin], [Net Revenue])", PCT, "Revenue"),
    M("Valid Orders", "CALCULATE(COUNTROWS(fct_orders), fct_orders[is_valid_order] = TRUE())", NUM, "Orders"),
    M("AOV", "DIVIDE([Gross Revenue], [Valid Orders])", INR, "Orders", "Gross revenue per valid order (before returns)."),
    M("Active Customers", "CALCULATE(DISTINCTCOUNT(fct_orders[user_id]), fct_orders[is_valid_order] = TRUE())", NUM, "Customers"),
    M("New Customers", "CALCULATE(COUNTROWS(fct_orders), fct_orders[is_first_order] = TRUE())", NUM, "Customers"),
    M("Repeat Order Share", "DIVIDE(CALCULATE([Valid Orders], fct_orders[customer_order_number] > 1), [Valid Orders])", PCT, "Orders"),
    M("RTO Rate", "DIVIDE(CALCULATE(COUNTROWS(fct_orders), fct_orders[is_rto] = TRUE()), COUNTROWS(fct_orders))", PCT, "Orders"),
    M("Return Rate (value)", "DIVIDE(SUM(fct_orders[returned_revenue]), [Gross Revenue])", PCT, "Orders"),
    M("COD Share", "DIVIDE(CALCULATE(COUNTROWS(fct_orders), fct_orders[payment_type] = \"COD\"), COUNTROWS(fct_orders))", PCT, "Orders"),
]
funnel_measures = [
    M("Sessions", "SUM(funnel_daily[sessions])", NUM, "Funnel"),
    M("Product View Sessions", "SUM(funnel_daily[product_view_sessions])", NUM, "Funnel"),
    M("Cart Sessions", "SUM(funnel_daily[cart_sessions])", NUM, "Funnel"),
    M("Checkout Sessions", "SUM(funnel_daily[checkout_sessions])", NUM, "Funnel"),
    M("Purchase Sessions", "SUM(funnel_daily[purchase_sessions])", NUM, "Funnel"),
    M("Conversion Rate", "DIVIDE([Purchase Sessions], [Sessions])", "0.00%", "Funnel", "Sessions with a purchase / non-bot sessions."),
    M("Product View → Cart", "DIVIDE([Cart Sessions], [Product View Sessions])", PCT, "Funnel"),
    M("Cart → Checkout", "DIVIDE([Checkout Sessions], [Cart Sessions])", PCT, "Funnel"),
    M("Checkout → Purchase", "DIVIDE([Purchase Sessions], [Checkout Sessions])", PCT, "Funnel"),
    M("Stage Sessions", "SWITCH(SELECTEDVALUE(funnel_stage[stage_order]), 1, [Sessions], 2, [Product View Sessions], "
      "3, [Cart Sessions], 4, [Checkout Sessions], 5, [Purchase Sessions])", NUM, "Funnel"),
    M("Stage % of Sessions", "DIVIDE([Stage Sessions], [Sessions])", PCT, "Funnel"),
]
ltv_measures = [
    M("LTV 12m Margin", "CALCULATE(AVERAGE(customer_ltv[margin_365d]), customer_ltv[eligible_365d] = TRUE())", INR, "LTV",
      "Avg gross margin within 365 days of first order; customers with a complete 365+30 day window only."),
    M("LTV 90d Margin", "CALCULATE(AVERAGE(customer_ltv[margin_90d]), customer_ltv[eligible_90d] = TRUE())", INR, "LTV"),
    M("First Order Margin", "AVERAGE(customer_ltv[margin_first_order])", INR, "LTV"),
    M("Repeat Rate 12m", "DIVIDE(CALCULATE(COUNTROWS(customer_ltv), customer_ltv[eligible_365d] = TRUE(), customer_ltv[orders_365d] >= 2), "
      "CALCULATE(COUNTROWS(customer_ltv), customer_ltv[eligible_365d] = TRUE()))", PCT, "LTV"),
    M("Customers (LTV)", "COUNTROWS(customer_ltv)", NUM, "LTV"),
    M("Historical Margin per Customer", "AVERAGE(customer_ltv[margin_to_date])", INR, "LTV"),
]
channel_measures = [
    M("Marketing Spend", "SUM(channel_monthly[spend_inr])", INR, "Acquisition"),
    M("Acquired Customers", "SUM(channel_monthly[new_customers])", NUM, "Acquisition"),
    M("CAC", f"DIVIDE(CALCULATE(SUM(channel_monthly[spend_inr]), channel_monthly[channel] IN {PAID}), "
             f"CALCULATE(SUM(channel_monthly[new_customers]), channel_monthly[channel] IN {PAID}))", INR, "Acquisition",
      "Acquisition cost / new customers (first touch). Paid channels only; email platform fees are not acquisition cost."),
    M("LTV:CAC (12m margin)", "DIVIDE([LTV 12m Margin], [CAC])", RATIO, "Acquisition"),
]
cohort_measures = [
    M("Retention %", "DIVIDE(SUM(cohort_retention[active_customers]), SUM(cohort_retention[cohort_size]))", PCT1, "Cohorts",
      "% of cohort placing a valid order in month k (observable months only)."),
    M("Cohort Customers", "SUM(cohort_retention[cohort_size])", NUM, "Cohorts"),
]
clv_measures = [
    M("Predicted Margin Next 12m", "AVERAGE(clv_predictions[predicted_margin_next_12m])", INR, "Predictive"),
    M("Total Predicted Margin", "SUM(clv_predictions[predicted_margin_next_12m])", INR, "Predictive"),
    M("Avg P(alive)", "AVERAGE(clv_predictions[p_alive])", PCT, "Predictive"),
    M("Scored Customers", "COUNTROWS(clv_predictions)", NUM, "Predictive"),
]

CHANNELS = [("Paid Social", "Paid", 1), ("Paid Search", "Paid", 2), ("Affiliate", "Paid", 3), ("Organic Search", "Unpaid", 4),
            ("Direct", "Unpaid", 5), ("Email", "Owned", 6), ("Organic Social", "Unpaid", 7), ("Referral", "Unpaid", 8),
            ("Unattributed", "Unknown", 9), ("Untracked", "Unknown", 10), ("Other Campaign", "Unknown", 11)]

tables = [
    csv_table("dim_date"),
    csv_table("dim_customers"),
    csv_table("fct_orders", orders_measures),
    csv_table("funnel_daily", funnel_measures),
    csv_table("channel_monthly", channel_measures),
    csv_table("cohort_retention", cohort_measures),
    csv_table("customer_ltv", ltv_measures, sort_by={"ltv_band": "ltv_band_order"}),
    csv_table("clv_predictions", clv_measures),
    csv_table("kpi_monthly"),
    static_table("dim_channel", [("channel", "string"), ("channel_type", "string"), ("sort_order", "int64")],
                 CHANNELS, sort_by={"channel": "sort_order"}),
    static_table("funnel_stage", [("stage", "string"), ("stage_order", "int64")],
                 [("1. Session", 1), ("2. Product view", 2), ("3. Add to cart", 3), ("4. Checkout", 4), ("5. Purchase", 5)],
                 sort_by={"stage": "stage_order"}),
]
for t in tables:  # drop the placeholder None sort keys
    for c in t["columns"]:
        if c.get("sortByColumn") is None:
            c.pop("sortByColumn", None)

relationships = [
    ("fct_orders", "order_date", "dim_date", "date_day"),
    ("fct_orders", "user_id", "dim_customers", "user_id"),
    ("funnel_daily", "session_date", "dim_date", "date_day"),
    ("funnel_daily", "channel", "dim_channel", "channel"),
    ("channel_monthly", "channel", "dim_channel", "channel"),
    ("channel_monthly", "month_start", "dim_date", "date_day"),
    ("dim_customers", "acquisition_channel", "dim_channel", "channel"),
    ("customer_ltv", "user_id", "dim_customers", "user_id"),
    ("clv_predictions", "user_id", "dim_customers", "user_id"),
]

model = {
    "name": NAME,
    "compatibilityLevel": 1567,
    "model": {
        "culture": "en-US",
        "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
        "defaultPowerBIDataSourceVersion": "powerBI_V3",
        "sourceQueryCulture": "en-US",
        "tables": tables,
        "relationships": [{"name": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{a}{b}{c}{d}")), "fromTable": a, "fromColumn": b,
                           "toTable": c, "toColumn": d} for a, b, c, d in relationships],
        "expressions": [{
            "name": "ExportFolder", "kind": "m",
            "expression": f'"{EXPORT_FOLDER}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]',
            "description": "Folder containing the dashboard CSV exports (must end with a backslash).",
        }],
        "annotations": [
            {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            {"name": "PBI_QueryOrder", "value": json.dumps(["ExportFolder"] + [t["name"] for t in tables])},
        ],
    },
}

# =============================================================================
# REPORT (PBIR-Legacy report.json)
# =============================================================================
_z = [0]


def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": f"'{v}'"}}}


def color(hex_):
    return {"solid": {"color": lit(hex_)}}


class Q:
    """Builds the prototypeQuery + projections for a visual from 'table.field' references."""

    def __init__(self):
        self.froms, self.selects, self.alias = [], [], {}

    def src(self, table):
        if table not in self.alias:
            a = f"t{len(self.alias)}"
            self.alias[table] = a
            self.froms.append({"Name": a, "Entity": table, "Type": 0})
        return self.alias[table]

    def field(self, ref):
        table, prop = ref.split(".", 1)
        measure = prop.startswith("[")
        prop = prop.strip("[]")
        kind = "Measure" if measure else "Column"
        sel = {kind: {"Expression": {"SourceRef": {"Source": self.src(table)}}, "Property": prop},
               "Name": f"{table}.{prop}", "NativeReferenceName": prop}
        if not any(s["Name"] == sel["Name"] for s in self.selects):
            self.selects.append(sel)
        return sel["Name"]

    def expr(self, ref):
        table, prop = ref.split(".", 1)
        kind = "Measure" if prop.startswith("[") else "Column"
        return {kind: {"Expression": {"SourceRef": {"Source": self.src(table)}}, "Property": prop.strip("[]")}}


def visual(vtype, x, y, w, h, roles=None, title=None, objects=None, vc=None, sort=None, filters=None):
    _z[0] += 1
    q = Q()
    projections = {}
    for role, refs in (roles or {}).items():
        projections[role] = [{"queryRef": q.field(r), **({"active": True} if role in ("Category", "Rows", "Values") and vtype == "slicer" else {})}
                             for r in refs]
    sv = {"visualType": vtype, "projections": projections, "drillFilterOtherVisuals": True}
    if q.selects:
        sv["prototypeQuery"] = {"Version": 2, "From": q.froms, "Select": q.selects}
        if sort:
            ref, direction = sort
            sv["prototypeQuery"]["OrderBy"] = [{"Direction": 1 if direction == "asc" else 2, "Expression": q.expr(ref)}]
    if objects:
        sv["objects"] = objects
    vco = dict(vc or {})
    if title:
        vco["title"] = [{"properties": {"show": lit(True), "text": lit(title), "fontColor": color(INK),
                                         "fontSize": lit(11), "bold": lit(True)}}]
    vco.setdefault("background", [{"properties": {"show": lit(True), "color": color("#FFFFFF"), "transparency": lit(0)}}])
    vco.setdefault("border", [{"properties": {"show": lit(True), "color": color("#E6E5E0"), "radius": lit(6)}}])
    sv["vcObjects"] = vco
    cfg = {"name": uuid.uuid4().hex[:20], "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": _z[0] * 1000, "width": w,
                                                                               "height": h, "tabOrder": _z[0] * 1000}}],
           "singleVisual": sv}
    return {"x": x, "y": y, "z": _z[0] * 1000, "width": w, "height": h, "config": json.dumps(cfg),
            "filters": json.dumps(filters or [])}


def text(x, y, w, h, runs_by_paragraph, bg=None):
    """runs_by_paragraph: list of paragraphs; each paragraph a list of (text, style dict)."""
    paragraphs = [{"textRuns": [{"value": t, "textStyle": {"fontFamily": "Segoe UI", **st}} for t, st in p]}
                  for p in runs_by_paragraph]
    vc = {"background": [{"properties": {"show": lit(bg is not None), "color": color(bg or "#FFFFFF")}}],
          "border": [{"properties": {"show": lit(False)}}]}
    return visual("textbox", x, y, w, h, objects={"general": [{"properties": {"paragraphs": paragraphs}}]}, vc=vc)


def H(t, size="20pt"):
    return [[(t, {"fontSize": size, "fontWeight": "bold", "color": INK})]]


def card(x, y, w, h, measure, label):
    return visual("card", x, y, w, h, {"Values": [measure]}, objects={
        "labels": [{"properties": {"color": color(INK), "fontSize": lit(20), "labelDisplayUnits": lit(0)}}],
        "categoryLabels": [{"properties": {"show": lit(False)}}]},
        title=label)


def slicer(x, y, w, h, ref, title, mode="Dropdown"):
    return visual("slicer", x, y, w, h, {"Values": [ref]}, title=title, objects={
        "data": [{"properties": {"mode": lit(mode)}}],
        "header": [{"properties": {"show": lit(False)}}]})


def series_colors(field_ref, mapping):
    """Fixed colour per category value ('colour follows the entity')."""
    table, col = field_ref.split(".")
    out = []
    for value, hex_ in mapping.items():
        out.append({"properties": {"fill": color(hex_)},
                    "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0, "Left": {"Column": {
                        "Expression": {"SourceRef": {"Entity": table}}, "Property": col}}, "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}})
    return out


def date_filter(start="2025-10-01", end="2026-09-30"):
    """Page filter: last 12 complete months by default (editable in the Filters pane)."""
    return [{"name": uuid.uuid4().hex[:20], "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "dim_date"}},
                                                                      "Property": "date_day"}},
             "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_date", "Type": 0}], "Where": [{"Condition": {"And": {
                 "Left": {"Comparison": {"ComparisonKind": 2, "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "date_day"}},
                                         "Right": {"Literal": {"Value": f"datetime'{start}T00:00:00'"}}}},
                 "Right": {"Comparison": {"ComparisonKind": 4, "Left": {"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "date_day"}},
                                          "Right": {"Literal": {"Value": f"datetime'{end}T00:00:00'"}}}}}}}]},
             "type": "Advanced", "howCreated": 1}]


CH_COLORS = {"Paid Search": BLUE, "Paid Social": ORANGE, "Organic Search": AQUA, "Direct": VIOLET, "Affiliate": YELLOW,
             "Email": MAGENTA, "Organic Social": GREEN, "Referral": RED, "Unattributed": GREY}
DEV_COLORS = {"mobile": ORANGE, "desktop": BLUE, "tablet": AQUA}
NOTE = {"fontSize": "9pt", "color": INK2}
SUB = {"fontSize": "10pt", "color": INK2}


def page(name, display, visuals, filters=None):
    return {"name": name, "displayName": display, "displayOption": 1, "width": 1280, "height": 720,
            "config": json.dumps({"objects": {"background": [{"properties": {"color": color(BG), "transparency": lit(0)}}]}}),
            "filters": json.dumps(filters or []), "visualContainers": visuals}


SYNTH = "Synthetic data · fictional brand Threadline · INR · margin = product gross margin"

# ---- Page 1: Executive overview ------------------------------------------------
p1 = [
    text(20, 8, 900, 52, [[("Executive overview", {"fontSize": "20pt", "fontWeight": "bold", "color": INK})],
                          [("Last 12 complete months (Oct 2025 – Sep 2026; change in Filters pane) · " + SYNTH, NOTE)]]),
    slicer(1000, 12, 260, 46, "dim_channel.channel", "Acquisition / session channel"),
    card(20, 70, 170, 90, "fct_orders.[Net Revenue]", "Net revenue"),
    card(200, 70, 170, 90, "fct_orders.[Valid Orders]", "Orders"),
    card(380, 70, 170, 90, "fct_orders.[Active Customers]", "Active customers"),
    card(560, 70, 170, 90, "funnel_daily.[Conversion Rate]", "Session conversion"),
    card(740, 70, 170, 90, "fct_orders.[AOV]", "AOV"),
    card(920, 70, 170, 90, "fct_orders.[Repeat Order Share]", "Repeat order share"),
    card(1100, 70, 160, 90, "customer_ltv.[LTV 12m Margin]", "12-month LTV (margin)"),
    visual("lineChart", 20, 172, 620, 260, {"Category": ["dim_date.month_start"], "Y": ["fct_orders.[Net Revenue]"]},
           title="Net revenue by month", sort=("dim_date.month_start", "asc"),
           objects={"dataPoint": [{"properties": {"fill": color(BLUE)}}]}),
    visual("funnel", 650, 172, 610, 260, {"Category": ["funnel_stage.stage"], "Y": ["funnel_daily.[Stage Sessions]"]},
           title="Session funnel: sessions reaching each stage", sort=("funnel_stage.stage", "asc"),
           objects={"dataPoint": [{"properties": {"fill": color(BLUE)}}]}),
    visual("clusteredBarChart", 20, 444, 400, 260, {"Category": ["dim_channel.channel"], "Y": ["fct_orders.[New Customers]"]},
           title="New customers by acquisition channel", sort=("fct_orders.[New Customers]", "desc"),
           objects={"dataPoint": series_colors("dim_channel.channel", CH_COLORS)}),
    visual("clusteredBarChart", 430, 444, 400, 260, {"Category": ["dim_channel.channel"], "Y": ["customer_ltv.[LTV 12m Margin]"]},
           title="12-month margin LTV per customer", sort=("customer_ltv.[LTV 12m Margin]", "desc"),
           objects={"dataPoint": series_colors("dim_channel.channel", CH_COLORS)}),
    text(840, 444, 420, 260, [
        [("What this page says", {"fontSize": "12pt", "fontWeight": "bold", "color": INK})],
        [("• Paid Social brings the most new customers but the lowest 12-month LTV (₹1,069 vs ₹1,473 for Paid Search).", SUB)],
        [("• Mobile is 81% of sessions; its checkout completion (53%) trails desktop (69%).", SUB)],
        [("• 68% of first-year revenue comes from the first order: converting one-time buyers is the main LTV lever.", SUB)],
        [("See the Recommendations page for actions.", NOTE)]], bg="#FFFFFF"),
]

# ---- Page 2: Funnel ---------------------------------------------------------------
p2 = [
    text(20, 8, 760, 52, [[("Funnel: where do we lose buyers?", {"fontSize": "20pt", "fontWeight": "bold", "color": INK})],
                          [("Non-bot sessions; stage = reached this stage or later · " + SYNTH, NOTE)]]),
    slicer(790, 12, 150, 46, "dim_channel.channel", "Channel"),
    slicer(950, 12, 150, 46, "funnel_daily.device_type", "Device"),
    slicer(1110, 12, 150, 46, "funnel_daily.visitor_type", "Visitor type"),
    card(20, 70, 300, 80, "funnel_daily.[Conversion Rate]", "Session → purchase"),
    card(330, 70, 300, 80, "funnel_daily.[Product View → Cart]", "Product view → cart"),
    card(640, 70, 300, 80, "funnel_daily.[Cart → Checkout]", "Cart → checkout"),
    card(950, 70, 310, 80, "funnel_daily.[Checkout → Purchase]", "Checkout → purchase"),
    visual("funnel", 20, 162, 500, 270, {"Category": ["funnel_stage.stage"], "Y": ["funnel_daily.[Stage Sessions]"]},
           title="Sessions by stage", sort=("funnel_stage.stage", "asc"),
           objects={"dataPoint": [{"properties": {"fill": color(BLUE)}}]}),
    visual("pivotTable", 530, 162, 730, 270, {"Rows": ["dim_channel.channel"], "Columns": ["funnel_daily.device_type"],
                                              "Values": ["funnel_daily.[Conversion Rate]"]},
           title="Session conversion by channel × device"),
    visual("lineChart", 20, 444, 820, 260, {"Category": ["dim_date.month_start"], "Series": ["funnel_daily.device_type"],
                                            "Y": ["funnel_daily.[Checkout → Purchase]"]},
           title="Checkout → purchase by month and device (mobile redesign shipped Aug 2025)",
           sort=("dim_date.month_start", "asc"), objects={"dataPoint": series_colors("funnel_daily.device_type", DEV_COLORS)}),
    text(850, 444, 410, 260, [
        [("Reading the funnel", {"fontSize": "12pt", "fontWeight": "bold", "color": INK})],
        [("• Biggest volume leak: product view → cart (~18% add to cart).", SUB)],
        [("• Biggest device gap: checkout → purchase, mobile 53% vs desktop 69%.", SUB)],
        [("• Mobile redesign: +9.6 pp vs desktop (difference-in-differences, 95% CI 6.6–12.7).", SUB)],
        [("• Scenario: +4 pp mobile checkout ≈ ₹13L net revenue / yr (assumption-based).", SUB)]], bg="#FFFFFF"),
]
p2_filters = date_filter("2024-01-01", "2026-09-30")

# ---- Page 3: Cohorts ----------------------------------------------------------------
heat = {"values": [{"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {
    "Input": {"Measure": {"Expression": {"SourceRef": {"Entity": "cohort_retention"}}, "Property": "Retention %"}},
    "FillRule": {"linearGradient2": {"min": {"color": {"Literal": {"Value": "'#F4F8FD'"}}},
                                     "max": {"color": {"Literal": {"Value": "'#256ABF'"}}},
                                     "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}}}}}}},
    "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": "cohort_retention.Retention %"}}]}
month_filter = [{"name": uuid.uuid4().hex[:20], "expression": {"Column": {"Expression": {"SourceRef": {"Entity": "cohort_retention"}}, "Property": "month_offset"}},
                 "filter": {"Version": 2, "From": [{"Name": "c", "Entity": "cohort_retention", "Type": 0}], "Where": [{"Condition": {"And": {
                     "Left": {"Comparison": {"ComparisonKind": 1, "Left": {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "month_offset"}}, "Right": {"Literal": {"Value": "0L"}}}},
                     "Right": {"Comparison": {"ComparisonKind": 4, "Left": {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "month_offset"}}, "Right": {"Literal": {"Value": "12L"}}}}}}}]},
                 "type": "Advanced", "howCreated": 1}]
p3 = [
    text(20, 8, 900, 52, [[("Cohorts: do customers come back?", {"fontSize": "20pt", "fontWeight": "bold", "color": INK})],
                          [("Cohort = month of first valid order · retention = % of cohort ordering in month k · fully observed months only · " + SYNTH, NOTE)]]),
    slicer(1000, 12, 260, 46, "cohort_retention.acquisition_channel", "Cohort channel (pick one; 'All' = everyone)"),
    visual("pivotTable", 20, 70, 760, 634, {"Rows": ["cohort_retention.cohort_month"], "Columns": ["cohort_retention.month_offset"],
                                            "Values": ["cohort_retention.[Retention %]"]},
           title="Monthly retention by first-order cohort (months 1–12)", objects=heat, filters=month_filter),
    visual("lineChart", 790, 70, 470, 300, {"Category": ["cohort_retention.month_offset"], "Series": ["cohort_retention.acquisition_channel"],
                                            "Y": ["cohort_retention.[Retention %]"]},
           title="Average retention curve by acquisition channel", sort=("cohort_retention.month_offset", "asc"),
           objects={"dataPoint": series_colors("cohort_retention.acquisition_channel", CH_COLORS)}, filters=month_filter),
    text(790, 380, 470, 324, [
        [("Reading the cohorts", {"fontSize": "12pt", "fontWeight": "bold", "color": INK})],
        [("• Monthly retention is low and decays smoothly (6–8% in month 1 → 1–2% by month 12): normal for apparel.", SUB)],
        [("• 27.5% of customers buy again within a year; median gap 76 days. Start the 2nd-purchase journey at day 30–40.", SUB)],
        [("• Paid Social customers repeat half as often (16.6% vs 31.2% for Paid Search within 365 days).", SUB)],
        [("• Blended retention looks flat because more Paid Social in the mix offsets steady within-channel retention (mix-adjusted cohorts would be 0.4–0.6 pp higher).", SUB)],
        [("Tip: select a single channel in the slicer above; the curve chart compares channels.", NOTE)]], bg="#FFFFFF"),
]

# ---- Page 4: Customer value & LTV ------------------------------------------------------
p4 = [
    text(20, 8, 900, 52, [[("Customer value: LTV, CAC and who to keep", {"fontSize": "20pt", "fontWeight": "bold", "color": INK})],
                          [("LTV = avg gross margin within 365 days of first order (complete windows only). CAC = paid acquisition cost / new customers · " + SYNTH, NOTE)]]),
    slicer(1000, 12, 260, 46, "dim_channel.channel", "Acquisition channel"),
    card(20, 70, 240, 80, "customer_ltv.[LTV 12m Margin]", "12-month margin LTV"),
    card(270, 70, 240, 80, "customer_ltv.[Repeat Rate 12m]", "12-month repeat rate"),
    card(520, 70, 240, 80, "channel_monthly.[CAC]", "CAC (paid channels)"),
    card(770, 70, 240, 80, "channel_monthly.[LTV:CAC (12m margin)]", "LTV:CAC (12m margin)"),
    card(1020, 70, 240, 80, "clv_predictions.[Predicted Margin Next 12m]", "Predicted margin next 12m"),
    visual("clusteredColumnChart", 20, 162, 620, 270, {"Category": ["dim_channel.channel"],
                                                        "Y": ["customer_ltv.[LTV 12m Margin]", "channel_monthly.[CAC]"]},
           title="12-month margin LTV vs CAC by channel (paid channels have CAC)", sort=("customer_ltv.[LTV 12m Margin]", "desc"),
           objects={"dataPoint": [{"properties": {"fill": color(BLUE)}, "selector": {"metadata": "customer_ltv.LTV 12m Margin"}},
                                  {"properties": {"fill": color(ORANGE)}, "selector": {"metadata": "channel_monthly.CAC"}}]}),
    visual("clusteredColumnChart", 650, 162, 610, 270, {"Category": ["customer_ltv.ltv_band"], "Y": ["customer_ltv.[Customers (LTV)]"]},
           title="Customers by historical margin to date", sort=("customer_ltv.ltv_band", "asc"),
           objects={"dataPoint": [{"properties": {"fill": color(BLUE)}}]}),
    visual("lineChart", 20, 444, 620, 260, {"Category": ["customer_ltv.cohort_quarter"], "Y": ["customer_ltv.[LTV 90d Margin]"]},
           title="90-day margin LTV by cohort quarter: stable over time", sort=("customer_ltv.cohort_quarter", "asc"),
           objects={"dataPoint": [{"properties": {"fill": color(BLUE)}}]}),
    visual("tableEx", 650, 444, 610, 260, {"Values": ["clv_predictions.value_segment", "clv_predictions.[Scored Customers]",
                                                      "clv_predictions.[Predicted Margin Next 12m]", "clv_predictions.[Total Predicted Margin]",
                                                      "clv_predictions.[Avg P(alive)]"]},
           title="Predicted value segments (MBG/NBD + Gamma-Gamma, validated on a holdout year)"),
]

# ---- Page 5: Recommendations --------------------------------------------------------------
B = {"fontSize": "11pt", "fontWeight": "bold", "color": INK}
p5 = [
    text(20, 8, 1240, 52, [[("Recommendations", {"fontSize": "20pt", "fontWeight": "bold", "color": INK})],
                           [("Prioritised by impact × effort × confidence. Impacts are labelled scenarios, not forecasts · " + SYNTH, NOTE)]]),
    text(20, 70, 610, 300, [
        [("1 · Re-base Paid Social on value, not volume (do now)", B)],
        [("Evidence: 29% of customers, 16.6% repeat, LTV:CAC 1.05× (Paid Search 1.64×). Marginal CAC after the 2025 ramp ₹1,250 > ₹1,069 12-month margin.", SUB)],
        [("Action: cap CAC at what margin supports, optimise Meta for value events, cut the marginal ~₹16.7L/yr after a holdout test confirms incrementality.", SUB)],
        [("", SUB)],
        [("2 · Keep fixing mobile checkout, with A/B tests (do now)", B)],
        [("Evidence: mobile checkout completion 53% vs desktop 69%; Aug-2025 redesign +9.6 pp (DiD).", SUB)],
        [("Action: UPI one-tap, address autofill, guest checkout. Scenario +4 pp ≈ ₹13L revenue / ₹7L margin a year.", SUB)]], bg="#FFFFFF"),
    text(650, 70, 610, 300, [
        [("3 · Second-purchase journey, day 30 → 90 (next)", B)],
        [("Evidence: 27.5% repeat within a year, median 76 days; 57% of first-year repeaters buy by day 90. A repeater adds ~₹1,640 margin.", SUB)],
        [("Action: CRM journey from day 30 with a holdout group; report retention by channel and mix-adjusted.", SUB)],
        [("", SUB)],
        [("4 · Judge sales and welcome offers on cohort value (test)", B)],
        [("Evidence: sale-acquired customers ₹649 vs ₹1,521 12-month margin; first-order returns cut repeat 29% → 22%.", SUB)],
        [("Action: evaluate sales on 90-day cohort margin; test free exchanges instead of a 10% welcome code; fit guidance.", SUB)]], bg="#FFFFFF"),
    text(20, 380, 1240, 324, [
        [("Opportunity matrix", B)],
        [("Mobile checkout (A/B)  —  Impact: High · Effort: Medium · Confidence: High  →  Priority 1", SUB)],
        [("Paid Social re-base + marginal spend cut  —  Impact: Medium · Effort: Low · Confidence: High (direction)  →  Priority 1", SUB)],
        [("Second-purchase CRM journey  —  Impact: Low–Medium (compounding) · Effort: Low · Confidence: Medium  →  Priority 2", SUB)],
        [("Mobile product page → cart +1 pp  —  Impact: Medium (~₹10L revenue) · Effort: Medium · Confidence: Medium  →  Priority 2", SUB)],
        [("Sale strategy / non-discount welcome offer  —  Impact: Medium · Effort: Low · Confidence: Medium  →  Priority 3", SUB)],
        [("COD → prepaid nudges in Tier-2/3 (22% COD RTO vs 2% prepaid)  —  Impact: Low–Medium · Effort: Low · Confidence: Medium  →  Priority 3", SUB)],
        [("", SUB)],
        [("Data needed next: incrementality tests (geo holdouts) and campaign-level spend; real fulfilment/RTO costs. "
          "Limitations: synthetic data; observational causality; predictive model over-predicts ~13% (use for ranking).", NOTE)]], bg="#FFFFFF"),
]

report = {
    "config": json.dumps({"version": "5.59", "activeSectionIndex": 0, "linguisticSchemaSyncVersion": 0,
                          "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": 1},
                          "objects": {"outspacePane": [{"properties": {"expanded": lit(False)}}]}}),
    "layoutOptimization": 0,
    "sections": [
        {**page("ReportSection1", "1 · Executive overview", p1, date_filter()), "ordinal": 0},
        {**page("ReportSection2", "2 · Funnel", p2, p2_filters), "ordinal": 1},
        {**page("ReportSection3", "3 · Cohorts", p3), "ordinal": 2},
        {**page("ReportSection4", "4 · Customer value & LTV", p4), "ordinal": 3},
        {**page("ReportSection5", "5 · Recommendations", p5), "ordinal": 4},
    ],
}

# =============================================================================
# WRITE
# =============================================================================
if __name__ == "__main__":
    if OUT.exists():
        shutil.rmtree(OUT)
    sm, rp = OUT / f"{NAME}.SemanticModel", OUT / f"{NAME}.Report"
    sm.mkdir(parents=True)
    rp.mkdir(parents=True)
    (OUT / f"{NAME}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}], "settings": {"enableAutoRecovery": True}}, indent=2),
        encoding="utf-8")
    (sm / "definition.pbism").write_text(json.dumps({"version": "1.0", "settings": {}}, indent=2), encoding="utf-8")
    (sm / "model.bim").write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
    (rp / "definition.pbir").write_text(json.dumps({"version": "1.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"},
                                                                                         "byConnection": None}}, indent=2), encoding="utf-8")
    (rp / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    n_vis = sum(len(s["visualContainers"]) for s in report["sections"])
    print(f"PBIP written to {OUT} ({len(tables)} tables, {sum(len(t.get('measures', [])) for t in tables)} measures, "
          f"{len(relationships)} relationships, {len(report['sections'])} pages, {n_vis} visuals)")
    print(f"ExportFolder parameter = {EXPORT_FOLDER}")
