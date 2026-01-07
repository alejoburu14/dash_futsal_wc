# pages/noncomp_medical.py
from __future__ import annotations
import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
import plotly.express as px
import pandas as pd
import os
from flask_login import current_user

dash.register_page(__name__, path="/medical", name="Dashboard · Medical")

def _load_injuries() -> pd.DataFrame:
    # 2nd data source example: CSV in assets (fallback to synthetic)
    path = "assets/injuries.csv"
    if os.path.exists(path):
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame({
            "Date": pd.date_range("2024-08-01", periods=40, freq="3D"),
            "Player": ["Player " + str(i%8+1) for i in range(40)],
            "Type": ["Muscle","Impact","Overuse","Joint"] * 10,
            "Severity": ["Minor","Moderate","Severe","Minor"] * 10,
            "DaysOut": [3,10,21,5]*10
        })
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def layout():
    if not current_user.is_authenticated:
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    df = _load_injuries()
    players = sorted(df["Player"].unique())
    types = sorted(df["Type"].unique())

    return html.Div([
        html.H3("Medical dashboard (Non-competitive area)"),
        dbc.Card(dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Player"),
                    dcc.Dropdown(id="md-player", options=[{"label":p,"value":p} for p in players],
                                 placeholder="All", clearable=True)
                ], md=4),
                dbc.Col([
                    dbc.Label("Injury type"),
                    dcc.Dropdown(id="md-type", options=[{"label":t,"value":t} for t in types],
                                 placeholder="All", clearable=True)
                ], md=4),
                dbc.Col([
                    dbc.Label("Date range"),
                    dcc.DatePickerRange(id="md-dates",
                                        start_date=df["Date"].min().date(),
                                        end_date=df["Date"].max().date())
                ], md=4),
            ])
        ])),

        dcc.Loading(dcc.Graph(id="md-graph1"), type="dot"),
        dcc.Loading(dcc.Graph(id="md-graph2"), type="dot"),

        html.Hr(),
        html.H5("Injuries table"),
        DataTable(
            id="md-table",
            columns=[{"name":c,"id":c} for c in ["Date","Player","Type","Severity","DaysOut"]],
            page_size=10,
            filter_action="native",
            sort_action="native",
            style_table={"overflowX":"auto"},
        )
    ])

@callback(
    Output("md-graph1","figure"),
    Output("md-graph2","figure"),
    Output("md-table","data"),
    Input("md-player","value"),
    Input("md-type","value"),
    Input("md-dates","start_date"),
    Input("md-dates","end_date"),
)
def _update_md(player, inj_type, start, end):
    df = _load_injuries()
    if start: df = df[df["Date"] >= pd.to_datetime(start)]
    if end:   df = df[df["Date"] <= pd.to_datetime(end)]
    if player: df = df[df["Player"]==player]
    if inj_type: df = df[df["Type"]==inj_type]

    # viz 1: injuries by type
    fig1 = px.histogram(df, x="Type", color="Severity", barmode="group", title="Injuries by type & severity")

    # viz 2: monthly injuries trend
    tmp = df.copy()
    tmp["Month"] = tmp["Date"].dt.to_period("M").astype(str)
    fig2 = px.histogram(tmp, x="Month", color="Type", barmode="group", title="Injuries per month")

    return fig1, fig2, df[["Date","Player","Type","Severity","DaysOut"]].to_dict("records")
