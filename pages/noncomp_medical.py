# pages/noncomp_medical.py
from __future__ import annotations
import os
import dash
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
import plotly.express as px
import pandas as pd
from flask_login import current_user

dash.register_page(__name__, path="/medical", name="Dashboard · Medical")


# ------------------ Data loading ------------------
def _load_injuries() -> pd.DataFrame:
    """Second data source: CSV in assets (fallback to synthetic)."""
    path = "assets/injuries.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame({
            "Date": pd.date_range("2024-08-01", periods=40, freq="3D"),
            "Player": [f"Player {i%8 + 1}" for i in range(40)],
            "Type": ["Muscle", "Impact", "Overuse", "Joint"] * 10,
            "Severity": ["Minor", "Moderate", "Severe", "Minor"] * 10,
            "DaysOut": [3, 10, 21, 5] * 10,
        })
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    return df


# ------------------ Layout ------------------
def layout():
    if not current_user.is_authenticated:
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    df = _load_injuries()
    players = sorted(df["Player"].dropna().unique())
    types = sorted(df["Type"].dropna().unique())
    dmin = df["Date"].min().date() if not df.empty else None
    dmax = df["Date"].max().date() if not df.empty else None

    return html.Div([
        html.H3("Medical dashboard"),

        # Filters (Date range FIRST for consistency with Performance page)
        dbc.Card(
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Date range"),
                        dcc.DatePickerRange(
                            id="md-dates",
                            start_date=dmin,
                            end_date=dmax,
                            min_date_allowed=dmin,
                            max_date_allowed=dmax,
                            display_format="YYYY-MM-DD",
                            persistence=True,
                            persistence_type="session",
                        ),
                    ], md=4),
                    dbc.Col([
                        dbc.Label("Player"),
                        dcc.Dropdown(
                            id="md-player",
                            options=[{"label": p, "value": p} for p in players],
                            placeholder="All",
                            clearable=True,
                            persistence=True,
                            persistence_type="session",
                        ),
                    ], md=4),
                    dbc.Col([
                        dbc.Label("Injury type"),
                        dcc.Dropdown(
                            id="md-type",
                            options=[{"label": t, "value": t} for t in types],
                            placeholder="All",
                            clearable=True,
                            persistence=True,
                            persistence_type="session",
                        ),
                    ], md=4),
                ])
            ])
        ),

        dcc.Loading(dcc.Graph(id="md-graph1"), type="dot"),
        dcc.Loading(dcc.Graph(id="md-graph2"), type="dot"),

        html.Hr(),
        html.H5("Injuries table"),

        # Scrollable table (no pagination)
        dcc.Loading(
            DataTable(
                id="md-table",
                columns=[{"name": c, "id": c} for c in ["Date", "Player", "Type", "Severity", "DaysOut"]],
                page_action="none",
                style_table={"height": "420px", "overflowY": "auto"},
                filter_action="native",
                sort_action="native",
                style_cell={"padding": "6px", "whiteSpace": "normal"},
                fixed_rows={"headers": True},
            ),
            type="dot",
        ),
    ])


# ------------------ Main update callback ------------------
@callback(
    Output("md-graph1", "figure"),
    Output("md-graph2", "figure"),
    Output("md-table", "data"),
    Input("md-player", "value"),
    Input("md-type", "value"),
    Input("md-dates", "start_date"),
    Input("md-dates", "end_date"),
)
def _update_md(player, inj_type, start, end):
    df = _load_injuries()

    # Filter by dates
    if start:
        df = df[df["Date"] >= pd.to_datetime(start)]
    if end:
        df = df[df["Date"] <= pd.to_datetime(end)]

    # Filter by player/type
    if player:
        df = df[df["Player"] == player]
    if inj_type:
        df = df[df["Type"] == inj_type]

    # Viz 1: injuries by type & severity
    fig1 = px.histogram(
        df, x="Type", color="Severity", barmode="group",
        title="Injuries by type & severity"
    )

    # Viz 2: monthly injuries trend
    tmp = df.copy()
    tmp["Month"] = pd.to_datetime(tmp["Date"], errors="coerce").dt.to_period("M").astype(str)
    fig2 = px.histogram(
        tmp, x="Month", color="Type", barmode="group",
        title="Injuries per month"
    )

    # Table data (pretty date)
    out = df.copy()
    if not out.empty:
        out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")

    return fig1, fig2, out[["Date", "Player", "Type", "Severity", "DaysOut"]].to_dict("records")
