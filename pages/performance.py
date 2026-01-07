# pages/performance.py
from __future__ import annotations
import io
from datetime import date
import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
import plotly.express as px
import plotly.graph_objects as go
from flask_login import current_user
import pandas as pd

from data import get_matches, get_match_events, get_players_for_teams, sort_matches, load_team_colors_db, pick_colors

dash.register_page(__name__, path="/performance", name="Dashboard · Performance")

def _filters(df_matches: pd.DataFrame):
    if df_matches.empty:
        return html.Div(dbc.Alert("No matches found.", color="warning"))
    # date options
    dates = sorted(d for d in df_matches["KickoffDate"].dropna().unique() if d)
    date_min = dates[0] if dates else ""
    date_max = dates[-1] if dates else ""
    teams = sorted(set(df_matches["HomeName"]).union(set(df_matches["AwayName"])))
    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Date range"),
                    dcc.DatePickerRange(
                        id="pf-date-range",
                        min_date_allowed=date.fromisoformat(date_min) if date_min else None,
                        max_date_allowed=date.fromisoformat(date_max) if date_max else None,
                        start_date=date.fromisoformat(date_min) if date_min else None,
                        end_date=date.fromisoformat(date_max) if date_max else None,
                        display_format="YYYY-MM-DD",
                    ),
                ], md=4),
                dbc.Col([
                    dbc.Label("Team"),
                    dcc.Dropdown(
                        id="pf-team",
                        options=[{"label":t, "value":t} for t in teams],
                        value=None,
                        placeholder="All teams",
                        clearable=True
                    ),
                ], md=4),
                dbc.Col([
                    dbc.Label("Match"),
                    dcc.Dropdown(id="pf-match", placeholder="Select a match…")
                ], md=4),
            ])
        ])
    )

def layout():
    if not current_user.is_authenticated:
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    df_matches = get_matches()
    df_matches = sort_matches(df_matches)

    return html.Div([
        html.H3("Performance dashboard"),
        _filters(df_matches),

        dcc.Store(id="pf-matches-store", data=df_matches.to_dict("records")),
        dcc.Loading(dcc.Graph(id="pf-graph1"), type="dot"),
        dcc.Loading(dcc.Graph(id="pf-graph2"), type="dot"),
        html.Div([
            dbc.Button("Export PDF", id="pf-export", color="secondary"),
            dcc.Download(id="pf-download"),
        ], className="mt-2"),
        html.Hr(),
        html.H5("Timeline (attacking actions only)"),
        dcc.Loading(
            DataTable(
                id="pf-table",
                columns=[{"name":c,"id":c} for c in ["TeamName","Description","MatchMinute","PlayerName"]],
                page_size=12,
                filter_action="native",
                sort_action="native",
                style_table={"overflowX":"auto"},
            ),
            type="dot"
        )
    ])

# Populate matches dropdown based on filters
@callback(
    Output("pf-match","options"),
    Input("pf-matches-store","data"),
    Input("pf-date-range","start_date"),
    Input("pf-date-range","end_date"),
    Input("pf-team","value"),
)
def _update_match_options(data, start_date, end_date, team):
    if not data: return []
    df = pd.DataFrame(data)
    if start_date: df = df[df["KickoffDate"] >= start_date]
    if end_date:   df = df[df["KickoffDate"] <= end_date]
    if team:
        df = df[(df["HomeName"]==team) | (df["AwayName"]==team)]
    return [{"label": f'{r["KickoffDate"]} · {r["MatchName"]}', "value": r["MatchId"]} for _,r in df.iterrows()]

# Load events & draw charts + table
@callback(
    Output("pf-graph1","figure"),
    Output("pf-graph2","figure"),
    Output("pf-table","data"),
    Input("pf-match","value"),
    State("pf-matches-store","data"),
    prevent_initial_call=True,
)
def _load_match(match_id, data):
    if not match_id or not data:
        raise dash.exceptions.PreventUpdate
    dfm = pd.DataFrame(data)
    row = dfm[dfm["MatchId"]==match_id]
    if row.empty:
        return go.Figure(), go.Figure(), []
    row = row.iloc[0]
    events = get_match_events(str(match_id))
    squads = get_players_for_teams([row["HomeId"], row["AwayId"]])
    # join names & keep attacking set
    name_map = {row["HomeId"]:row["HomeName"], row["AwayId"]:row["AwayName"]}
    df = events.copy()
    df["TeamName"] = df["TeamId"].map(name_map)
    if not squads.empty:
        df = df.merge(squads[["PlayerId","PlayerName"]], on="PlayerId", how="left")
    df = df[df["Description"].isin(["Attempt at Goal","Goal!"])].copy()
    # minute int
    df["m"] = df["MatchMinute"].astype(str).str.extract(r"(\d+)").fillna("0").astype(int)

    # colors
    colors_db = load_team_colors_db()
    hc, ac = pick_colors(row["HomeName"], row["AwayName"], colors_db)
    colors = {row["HomeName"]: hc, row["AwayName"]: ac}

    # Chart 1: Attempts & Goals per minute (grouped)
    fig1 = px.histogram(df, x="m", color="TeamName", nbins=40,
                        color_discrete_map=colors,
                        barmode="overlay",
                        labels={"m":"Minute","count":"Events"})
    fig1.update_layout(title=f"Events per minute — {row['MatchName']} ({row['KickoffDate']})", legend_title="Team")

    # Chart 2: Distribution by type
    fig2 = px.histogram(df, x="Description", color="TeamName",
                        color_discrete_map=colors, barmode="group")
    fig2.update_layout(title="Event distribution (Attempt vs Goal)", legend_title="Team")

    return fig1, fig2, df[["TeamName","Description","MatchMinute","PlayerName"]].fillna("").to_dict("records")

# Export to PDF (two charts)
@callback(
    Output("pf-download","data"),
    Input("pf-export","n_clicks"),
    State("pf-graph1","figure"),
    State("pf-graph2","figure"),
    prevent_initial_call=True,
)
def _export_pdf(n, fig1, fig2):
    # Create a simple PDF by rendering the figures to PNG (kaleido) and embedding
    import plotly.io as pio
    from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    # render images
    png1 = pio.to_image(fig1, format="png", scale=2)
    png2 = pio.to_image(fig2, format="png", scale=2)

    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph("Performance dashboard — Export", styles["Title"]), Spacer(1, 12)]
    for png in (png1, png2):
        img_buf = io.BytesIO(png)
        story += [Image(img_buf, width=500, height=300), Spacer(1, 12)]
    doc.build(story)
    return dcc.send_bytes(lambda x: x.write(buf.getvalue()), filename="performance.pdf")
