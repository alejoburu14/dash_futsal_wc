# pages/performance.py
from __future__ import annotations
import io
from datetime import date
import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
import plotly.express as px
import plotly.graph_objects as go
from flask_login import current_user
import pandas as pd

from data import (
    get_matches,
    get_match_events,
    get_players_for_teams,
    sort_matches,
    load_team_colors_db,
    pick_colors,
)

dash.register_page(__name__, path="/performance", name="Dashboard · Performance")


# ---------- helpers for robust date handling ----------
def _derive_date_bounds(df_matches: pd.DataFrame) -> tuple[date, date]:
    """
    Return (min_date, max_date) as Python date objects from matches.
    Works with ISO strings like '2024-09-14T15:00:00Z' or plain dates.
    Prefer 'LocalDate' if present, else 'KickoffDate'.
    """
    if df_matches.empty:
        today = date.today()
        return today, today

    col = "LocalDate" if "LocalDate" in df_matches.columns else "KickoffDate"
    s = pd.to_datetime(df_matches[col], utc=True, errors="coerce").dt.date
    dmin, dmax = s.min(), s.max()
    if pd.isna(dmin) or pd.isna(dmax):
        today = date.today()
        dmin = dmin if not pd.isna(dmin) else today
        dmax = dmax if not pd.isna(dmax) else today
    return dmin, dmax


def _with_date_only(df_matches: pd.DataFrame) -> pd.DataFrame:
    """
    Add a normalized date column 'KickoffDateOnly' (Python date),
    computed from LocalDate or KickoffDate.
    """
    df = df_matches.copy()
    col = "LocalDate" if "LocalDate" in df.columns else "KickoffDate"
    df["KickoffDateOnly"] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.date
    return df


# ---------- UI blocks ----------
def _filters(df_matches: pd.DataFrame):
    if df_matches.empty:
        return html.Div(dbc.Alert("No matches found.", color="warning"))

    dmin, dmax = _derive_date_bounds(df_matches)
    teams = sorted(set(df_matches["HomeName"]).union(set(df_matches["AwayName"])))

    return dbc.Card(
        dbc.CardBody(
            [
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Label("Date range"),
                                dcc.DatePickerRange(
                                    id="pf-date-range",
                                    min_date_allowed=dmin,
                                    max_date_allowed=dmax,
                                    start_date=dmin,
                                    end_date=dmax,
                                    display_format="YYYY-MM-DD",
                                ),
                            ],
                            md=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Team"),
                                dcc.Dropdown(
                                    id="pf-team",
                                    options=[{"label": t, "value": t} for t in teams],
                                    value=None,
                                    placeholder="All teams",
                                    clearable=True,
                                ),
                            ],
                            md=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Label("Match"),
                                dcc.Dropdown(id="pf-match", placeholder="Select a match…"),
                            ],
                            md=4,
                        ),
                    ]
                )
            ]
        )
    )


def layout():
    if not current_user.is_authenticated:
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    df_matches = get_matches()
    df_matches = sort_matches(df_matches)
    df_matches = _with_date_only(df_matches)  # <- normalize date for filtering

    return html.Div(
        [
            html.H3("Performance dashboard"),
            _filters(df_matches),
            dcc.Store(id="pf-matches-store", data=df_matches.to_dict("records")),
            dcc.Loading(dcc.Graph(id="pf-graph1"), type="dot"),
            dcc.Loading(dcc.Graph(id="pf-graph2"), type="dot"),
            html.Div(
                [
                    dbc.Button("Export PDF", id="pf-export", color="secondary"),
                    dcc.Download(id="pf-download"),
                ],
                className="mt-2",
            ),
            html.Hr(),
            html.H5("Timeline (attacking actions only)"),
            dcc.Loading(
                DataTable(
                    id="pf-table",
                    columns=[
                        {"name": c, "id": c}
                        for c in ["TeamName", "Description", "MatchMinute", "PlayerName"]
                    ],
                    page_size=12,
                    filter_action="native",
                    sort_action="native",
                    style_table={"overflowX": "auto"},
                ),
                type="dot",
            ),
        ]
    )


# ---------- Callbacks ----------
# Populate matches dropdown based on filters
@callback(
    Output("pf-match", "options"),
    Input("pf-matches-store", "data"),
    Input("pf-date-range", "start_date"),
    Input("pf-date-range", "end_date"),
    Input("pf-team", "value"),
)
def _update_match_options(data, start_date, end_date, team):
    if not data:
        return []

    df = pd.DataFrame(data)

    # Ensure the normalized date column is typed as date
    df["KickoffDateOnly"] = pd.to_datetime(
        df["KickoffDateOnly"], errors="coerce"
    ).dt.date

    s_date = pd.to_datetime(start_date, errors="coerce").date() if start_date else None
    e_date = pd.to_datetime(end_date, errors="coerce").date() if end_date else None

    if s_date:
        df = df[df["KickoffDateOnly"] >= s_date]
    if e_date:
        df = df[df["KickoffDateOnly"] <= e_date]
    if team:
        df = df[(df["HomeName"] == team) | (df["AwayName"] == team)]

    # Label shows normalized date for clarity
    return [
        {
            "label": f'{r["KickoffDateOnly"]} · {r["MatchName"]}',
            "value": r["MatchId"],
        }
        for _, r in df.iterrows()
    ]


# Load events & draw charts + table
@callback(
    Output("pf-graph1", "figure"),
    Output("pf-graph2", "figure"),
    Output("pf-table", "data"),
    Input("pf-match", "value"),
    State("pf-matches-store", "data"),
    prevent_initial_call=True,
)
def _load_match(match_id, data):
    if not match_id or not data:
        raise dash.exceptions.PreventUpdate

    dfm = pd.DataFrame(data)
    row = dfm[dfm["MatchId"] == match_id]
    if row.empty:
        return go.Figure(), go.Figure(), []
    row = row.iloc[0]

    events = get_match_events(str(match_id))
    squads = get_players_for_teams([row["HomeId"], row["AwayId"]])

    name_map = {row["HomeId"]: row["HomeName"], row["AwayId"]: row["AwayName"]}
    df = events.copy()
    df["TeamName"] = df["TeamId"].map(name_map)
    if not squads.empty:
        df = df.merge(squads[["PlayerId", "PlayerName"]], on="PlayerId", how="left")
    df = df[df["Description"].isin(["Attempt at Goal", "Goal!"])].copy()

    # minute int
    df["m"] = df["MatchMinute"].astype(str).str.extract(r"(\d+)").fillna("0").astype(int)

    # colors
    colors_db = load_team_colors_db()
    hc, ac = pick_colors(row["HomeName"], row["AwayName"], colors_db)
    colors = {row["HomeName"]: hc, row["AwayName"]: ac}

    # Chart 1: Attempts & Goals per minute (grouped)
    fig1 = px.histogram(
        df,
        x="m",
        color="TeamName",
        nbins=40,
        color_discrete_map=colors,
        barmode="overlay",
        labels={"m": "Minute", "count": "Events"},
    )
    fig1.update_layout(
        title=f"Events per minute — {row['MatchName']} ({row.get('KickoffDateOnly', '')})",
        legend_title="Team",
    )

    # Chart 2: Distribution by type
    fig2 = px.histogram(
        df, x="Description", color="TeamName", color_discrete_map=colors, barmode="group"
    )
    fig2.update_layout(title="Event distribution (Attempt vs Goal)", legend_title="Team")

    return (
        fig1,
        fig2,
        df[["TeamName", "Description", "MatchMinute", "PlayerName"]]
        .fillna("")
        .to_dict("records"),
    )


# Export to PDF (two charts)
@callback(
    Output("pf-download", "data"),
    Input("pf-export", "n_clicks"),
    State("pf-graph1", "figure"),
    State("pf-graph2", "figure"),
    prevent_initial_call=True,
)
def _export_pdf(n, fig1, fig2):
    import plotly.io as pio
    from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
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
