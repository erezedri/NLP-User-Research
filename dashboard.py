"""
dashboard.py — Plotly Dash two-phase review intelligence dashboard.

Phase 1: Good Experience (green theme)  — donut + bar + sample cards
Phase 2: Bad Experience  (red/orange)   — donut + bar + sample cards

Global KPI bar: Total | Good | Bad | Satisfaction % | Complaint %

Known pitfalls:
    - Port 8050 may be held from a previous run.
      Kill it: Get-NetTCPConnection -LocalPort 8050 | Stop-Process
    - pandas groupby().apply() drops columns in newer pandas.
      Use drop_duplicates(subset="tag") for sample selection instead.
    - UnicodeEncodeError on Hebrew/non-ASCII paths: add
      sys.stdout.reconfigure(encoding="utf-8") at script entry point.
"""

import logging
import sys
import webbrowser
import threading
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette (override per company as needed)
# ---------------------------------------------------------------------------
GREEN_DARK = "#1a7a4a"
GREEN_MID = "#27ae60"
GREEN_LIGHT = "#d5f5e3"
RED_DARK = "#b03a2e"
RED_MID = "#e74c3c"
RED_LIGHT = "#fadbd8"
BG = "#f8f9fa"
CARD_BG = "#ffffff"
TEXT_DARK = "#1c2833"
TEXT_MUTED = "#5d6d7e"
BORDER = "#dce1e7"

GREENS = ["#1a7a4a", "#229954", "#27ae60", "#2ecc71", "#58d68d",
          "#82e0aa", "#abebc6", "#d5f5e3"]
REDS = ["#b03a2e", "#c0392b", "#e74c3c", "#e67e22", "#f1948a"]


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _kpi_card(value: Any, label: str, color: str, bg: str) -> html.Div:
    return html.Div([
        html.Div(str(value), style={"fontSize": "2.4rem", "fontWeight": "800",
                                    "color": color, "lineHeight": "1"}),
        html.Div(label, style={"fontSize": "0.82rem", "color": TEXT_MUTED,
                               "marginTop": "4px", "fontWeight": "500"}),
    ], style={"background": bg, "borderRadius": "12px", "padding": "20px 28px",
              "border": f"1px solid {BORDER}", "minWidth": "140px",
              "textAlign": "center", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"})


def _review_card(text: str, tag: str, color: str, bg: str) -> html.Div:
    short = text[:220] + ("…" if len(text) > 220 else "")
    return html.Div([
        html.Div(f'"{short}"', style={"fontSize": "0.87rem", "color": TEXT_DARK,
                                      "fontStyle": "italic", "lineHeight": "1.55"}),
        html.Span(tag, style={"display": "inline-block", "marginTop": "10px",
                              "background": bg, "color": color, "borderRadius": "20px",
                              "padding": "3px 12px", "fontSize": "0.75rem",
                              "fontWeight": "600"}),
    ], style={"background": CARD_BG, "borderRadius": "10px", "padding": "16px 20px",
              "border": f"1.5px solid {BORDER}", "marginBottom": "10px",
              "boxShadow": "0 1px 4px rgba(0,0,0,0.05)"})


def _section_title(text: str, color: str) -> html.H3:
    return html.H3(text, style={"color": color, "fontWeight": "700",
                                "marginBottom": "14px", "marginTop": "0",
                                "fontSize": "1.05rem", "letterSpacing": "0.3px"})


def _phase_header(num: int, label: str, color: str, bg_col: str) -> html.Div:
    return html.Div([
        html.Div(f"Phase {num}", style={"fontSize": "0.72rem", "fontWeight": "700",
                                        "letterSpacing": "2px", "color": color,
                                        "textTransform": "uppercase", "marginBottom": "4px"}),
        html.H2(label, style={"margin": "0", "fontSize": "1.55rem",
                               "fontWeight": "800", "color": TEXT_DARK}),
    ], style={"background": bg_col, "borderRadius": "14px", "padding": "22px 30px",
              "marginBottom": "20px", "border": f"2px solid {color}",
              "boxShadow": "0 4px 14px rgba(0,0,0,0.07)"})


def _chart_card(*children: Any) -> html.Div:
    return html.Div(list(children), style={
        "background": CARD_BG, "borderRadius": "12px", "padding": "18px 20px",
        "border": f"1px solid {BORDER}", "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
    })


DIVIDER = html.Hr(style={"border": "none", "borderTop": f"2px dashed {BORDER}",
                          "margin": "36px 0"})


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_app(
    excel_path: str | Path,
    company_name: str = "Company",
    port: int = 8050,
) -> Dash:
    """
    Load the Excel output from excel_builder and construct the Dash app.

    Args:
        excel_path: path to the .xlsx file produced by excel_builder.write_excel()
        company_name: displayed in the dashboard header
        port: local port to serve on

    Returns:
        Configured Dash app (call .run() to start).
    """
    import openpyxl  # local import — only needed here

    sys.stdout.reconfigure(encoding="utf-8")

    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active

    records = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[2]:
            records.append({
                "persona": row[0],
                "review": str(row[1] or ""),
                "classification": row[2],
                "tag": row[3],
            })

    df = pd.DataFrame(records)
    good = df[df["classification"] == "Good Experience"].copy()
    bad = df[df["classification"] == "Bad Experience"].copy()
    total = len(df)
    n_good = len(good)
    n_bad = len(bad)

    # ── Good charts ──────────────────────────────────────────────────────────
    tag_good = good["tag"].value_counts().reset_index()
    tag_good.columns = ["tag", "count"]
    tag_good["tag_display"] = tag_good.apply(
        lambda r: r["tag"] if r["count"] >= 3 else "Other Positives", axis=1
    )
    tag_good = tag_good.groupby("tag_display", as_index=False)["count"].sum()
    tag_good = tag_good.sort_values("count", ascending=False)

    fig_good_donut = go.Figure(go.Pie(
        labels=tag_good["tag_display"], values=tag_good["count"], hole=0.62,
        marker_colors=GREENS[:len(tag_good)], textinfo="percent",
        hovertemplate="%{label}: %{value} reviews<extra></extra>",
    ))
    fig_good_donut.update_layout(
        showlegend=True, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=0, r=0, t=10, b=10), height=300,
        font=dict(family="Inter, sans-serif", size=11),
        legend=dict(orientation="v", x=1.02, y=0.5, font_size=11),
        annotations=[dict(text=f"<b>{n_good}</b><br>Good", x=0.5, y=0.5,
                          font_size=16, showarrow=False, font_color=GREEN_DARK)],
    )

    fig_good_bar = px.bar(
        tag_good, x="count", y="tag_display", orientation="h",
        color="tag_display", color_discrete_sequence=GREENS,
        labels={"count": "Reviews", "tag_display": ""},
    )
    fig_good_bar.update_layout(
        showlegend=False, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=0, r=10, t=10, b=10), height=300,
        font=dict(family="Inter, sans-serif", size=12),
        xaxis=dict(gridcolor="#eef0f2"), yaxis=dict(autorange="reversed"),
    )
    fig_good_bar.update_traces(marker_line_width=0)

    # ── Bad charts ───────────────────────────────────────────────────────────
    tag_bad = bad["tag"].value_counts().reset_index()
    tag_bad.columns = ["tag", "count"]
    tag_bad = tag_bad.sort_values("count", ascending=False)

    fig_bad_donut = go.Figure(go.Pie(
        labels=tag_bad["tag"], values=tag_bad["count"], hole=0.62,
        marker_colors=REDS[:len(tag_bad)], textinfo="percent",
        hovertemplate="%{label}: %{value} reviews<extra></extra>",
    ))
    fig_bad_donut.update_layout(
        showlegend=True, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=0, r=0, t=10, b=10), height=260,
        font=dict(family="Inter, sans-serif", size=11),
        legend=dict(orientation="v", x=1.02, y=0.5, font_size=11),
        annotations=[dict(text=f"<b>{n_bad}</b><br>Bad", x=0.5, y=0.5,
                          font_size=16, showarrow=False, font_color=RED_DARK)],
    )

    fig_bad_bar = px.bar(
        tag_bad, x="count", y="tag", orientation="h",
        color="tag", color_discrete_sequence=REDS,
        labels={"count": "Reviews", "tag": ""},
    )
    fig_bad_bar.update_layout(
        showlegend=False, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=0, r=10, t=10, b=10), height=260,
        font=dict(family="Inter, sans-serif", size=12),
        xaxis=dict(gridcolor="#eef0f2"), yaxis=dict(autorange="reversed"),
    )
    fig_bad_bar.update_traces(marker_line_width=0)

    # ── Sample reviews (drop_duplicates avoids pandas groupby column drop bug)
    top_good_tags = tag_good.nlargest(6, "count")["tag_display"].tolist()
    good_samples = (good[good["tag"].isin(top_good_tags)]
                    .drop_duplicates(subset="tag").head(6).reset_index(drop=True))
    bad_samples = bad.drop_duplicates(subset="tag").reset_index(drop=True)

    # ── App layout ───────────────────────────────────────────────────────────
    app = Dash(__name__, title=f"{company_name} · Review Intelligence")

    app.layout = html.Div(style={"fontFamily": "Inter, Segoe UI, sans-serif",
                                  "background": BG, "minHeight": "100vh"}, children=[
        html.Div([
            html.Div([
                html.Span(company_name, style={"fontWeight": "800", "fontSize": "1.35rem",
                                               "color": CARD_BG}),
                html.Span(" · Review Intelligence Dashboard",
                          style={"fontWeight": "400", "fontSize": "1rem",
                                 "color": "rgba(255,255,255,0.75)", "marginLeft": "6px"}),
            ]),
            html.Div([
                html.Span("Total reviews analysed: ", style={"color": "rgba(255,255,255,0.7)",
                                                              "fontSize": "0.88rem"}),
                html.Span(str(total), style={"color": CARD_BG, "fontWeight": "700",
                                             "fontSize": "0.88rem"}),
            ]),
        ], style={"background": f"linear-gradient(135deg, {GREEN_DARK} 0%, #1a4a7a 100%)",
                  "padding": "18px 40px", "display": "flex",
                  "justifyContent": "space-between", "alignItems": "center"}),

        html.Div(style={"maxWidth": "1200px", "margin": "0 auto",
                        "padding": "32px 24px"}, children=[
            html.Div([
                _kpi_card(total, "Total Reviews", TEXT_DARK, CARD_BG),
                _kpi_card(n_good, "Good Experience", GREEN_DARK, GREEN_LIGHT),
                _kpi_card(n_bad, "Bad Experience", RED_DARK, RED_LIGHT),
                _kpi_card(f"{round(n_good / total * 100)}%", "Satisfaction Rate",
                          GREEN_DARK, GREEN_LIGHT),
                _kpi_card(f"{round(n_bad / total * 100)}%", "Complaint Rate",
                          RED_DARK, RED_LIGHT),
            ], style={"display": "flex", "gap": "14px", "flexWrap": "wrap",
                      "marginBottom": "32px"}),

            _phase_header(1, "What are users happy about?", GREEN_MID, GREEN_LIGHT),
            html.Div([
                html.Div([_section_title("Tag Distribution", GREEN_DARK),
                          dcc.Graph(figure=fig_good_donut, config={"displayModeBar": False})],
                         style={"flex": "1", **_chart_card().style}),
                html.Div([_section_title("Positive Themes · Volume", GREEN_DARK),
                          dcc.Graph(figure=fig_good_bar, config={"displayModeBar": False})],
                         style={"flex": "2", **_chart_card().style}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "20px"}),
            html.Div([_section_title("Sample Positive Reviews", GREEN_DARK),
                      html.Div([_review_card(r["review"], r["tag"], GREEN_DARK, GREEN_LIGHT)
                                for _, r in good_samples.iterrows()])],
                     style={**_chart_card().style}),

            DIVIDER,

            _phase_header(2, "What are users complaining about?", RED_MID, RED_LIGHT),
            html.Div([
                html.Div([_section_title("Issue Distribution", RED_DARK),
                          dcc.Graph(figure=fig_bad_donut, config={"displayModeBar": False})],
                         style={"flex": "1", **_chart_card().style}),
                html.Div([_section_title("Complaint Categories · Volume", RED_DARK),
                          dcc.Graph(figure=fig_bad_bar, config={"displayModeBar": False})],
                         style={"flex": "2", **_chart_card().style}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "20px"}),
            html.Div([_section_title("Sample Complaints", RED_DARK),
                      html.Div([_review_card(r["review"], r["tag"], RED_DARK, RED_LIGHT)
                                for _, r in bad_samples.iterrows()])],
                     style={**_chart_card().style}),

            html.Div("Data: Trustpilot · Scraped via Apify",
                     style={"textAlign": "center", "color": TEXT_MUTED,
                            "fontSize": "0.78rem", "marginTop": "40px",
                            "paddingBottom": "24px"}),
        ]),
    ])

    return app


def run_dashboard(
    excel_path: str | Path,
    company_name: str = "Company",
    port: int = 8050,
    open_browser: bool = True,
) -> None:
    """Build and serve the dashboard. Blocking call."""
    app = build_app(excel_path, company_name=company_name, port=port)
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(debug=False, port=port)
