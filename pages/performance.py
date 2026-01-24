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
    """Return (min_date, max_date) as Python date objects."""
    if df_matches.empty:
        today = date.today()
        return today, today
    col = "LocalDate" if "LocalDate" in df_matches.columns else "KickoffDate"
    s = pd.to_datetime(df_matches[col], utc=True, errors="coerce").dt.date
    dmin, dmax = s.min(), s.max()
    if pd.isna(dmin) or pd.isna(dmax):
        today = date.today()
        if pd.isna(dmin): dmin = today
        if pd.isna(dmax): dmax = today
    return dmin, dmax


def _with_date_only(df_matches: pd.DataFrame) -> pd.DataFrame:
    """Add normalized date column used by filters and labels."""
    df = df_matches.copy()
    col = "LocalDate" if "LocalDate" in df.columns else "KickoffDate"
    df["KickoffDateOnly"] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.date
    return df


# ---------- UI block (single, correct definition) ----------
def _filters(df_matches: pd.DataFrame):
    if df_matches.empty:
        return html.Div(dbc.Alert("No matches found.", color="warning"))

    dmin, dmax = _derive_date_bounds(df_matches)
    teams = sorted(set(df_matches["HomeName"]).union(set(df_matches["AwayName"])))

    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Date range"),
                    dcc.DatePickerRange(
                        id="pf-date-range",
                        min_date_allowed=dmin,
                        max_date_allowed=dmax,
                        start_date=dmin,
                        end_date=dmax,
                        display_format="YYYY-MM-DD",
                        persistence=True,
                        persistence_type="session",
                    ),
                ], md=4),
                dbc.Col([
                    dbc.Label("Team"),
                    dcc.Dropdown(
                        id="pf-team",
                        options=[{"label": t, "value": t} for t in teams],
                        value=None,
                        placeholder="All teams",
                        clearable=True,
                        persistence=True,
                        persistence_type="session",
                    ),
                    dbc.FormText(
                        "Select a team to see its matches.",
                        color="secondary", className="mt-1"
                    ),
                ], md=4),
                dbc.Col([
                    dbc.Label("Match"),
                    dcc.Dropdown(
                        id="pf-match",
                        placeholder="Select a match",
                        persistence=True,
                        persistence_type="session",
                    ),
                    dbc.FormText(
                        "Select a match to see its attacking events.",
                        color="secondary", className="mt-1"
                    ),
                ], md=4),
            ])
        ])
    )


def layout():
    if not current_user.is_authenticated:
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    df_matches = get_matches()
    df_matches = sort_matches(df_matches)
    df_matches = _with_date_only(df_matches)     # <-- ensure KickoffDateOnly exists

    # placeholder figures so the front-end never sees undefined titles
    empty_fig = go.Figure()
    empty_fig.update_layout(title_text="", template="plotly_white")

    return html.Div([
        html.H3("Performance dashboard"),
        _filters(df_matches),

        dcc.Store(id="pf-matches-store", data=df_matches.to_dict("records")),
        dcc.Store(id="pf-selected-match", storage_type="session"),

        dcc.Loading(dcc.Graph(id="pf-graph1", figure=empty_fig), type="dot"),
        dcc.Loading(dcc.Graph(id="pf-graph2", figure=empty_fig), type="dot"),

        html.Div([
            dbc.Button("Export PDF", id="pf-export", color="secondary"),
            dcc.Download(id="pf-download"),
        ], className="mt-2"),

        html.Hr(),
        html.H5("Timeline (attacking events only)"),
        dcc.Loading(
            DataTable(
                id="pf-table",
                columns=[{"name": c, "id": c}
                         for c in ["TeamName", "Description", "MatchMinute", "PlayerName"]],
                page_action="none",                                 # scroll instead of pagination
                style_table={"height": "420px", "overflowY": "auto"},
                filter_action="native",
                sort_action="native",
                style_cell={"padding": "6px", "whiteSpace": "normal"},
                fixed_rows={"headers": True},
            ),
            type="dot"
        ),
    ])


# ---------- Callbacks ----------
@callback(
    Output("pf-selected-match", "data"),
    Input("pf-match", "value"),
    prevent_initial_call=True,
)
def _remember_match(match_id):
    # store the selected match id in session storage
    return match_id

@callback(
    Output("pf-match", "value"),
    Input("pf-match", "options"),
    State("pf-selected-match", "data"),
    prevent_initial_call=False,  # let it run on first load, harmless if nothing stored
)
def _restore_match_value(options, stored_match_id):
    if not options:
        return dash.no_update
    if not stored_match_id:
        return dash.no_update
    # Only restore if the stored id is still present in the new options
    option_values = {opt["value"] for opt in options if "value" in opt}
    if stored_match_id in option_values:
        return stored_match_id
    return dash.no_update


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

    # Build a robust, typed date column no matter what came from the store
    base = None
    if "KickoffDateOnly" in df.columns:
        base = df["KickoffDateOnly"]
    elif "LocalDate" in df.columns:
        base = df["LocalDate"]
    else:
        base = df["KickoffDate"]

    df["KDO"] = pd.to_datetime(base, utc=True, errors="coerce").dt.date  # <- real date objects

    s_date = pd.to_datetime(start_date, errors="coerce").date() if start_date else None
    e_date = pd.to_datetime(end_date, errors="coerce").date() if end_date else None

    if s_date:
        df = df[df["KDO"] >= s_date]
    if e_date:
        df = df[df["KDO"] <= e_date]
    if team:
        df = df[(df["HomeName"] == team) | (df["AwayName"] == team)]

    # Use normalized date in the label to avoid mixed formats
    return [
        {"label": f'{r["KDO"]} · {r["MatchName"]}', "value": r["MatchId"]}
        for _, r in df.iterrows()
    ]



@callback(
    Output("pf-graph1", "figure"),
    Output("pf-graph2", "figure"),
    Output("pf-table", "data"),
    Input("pf-match", "value"),
    State("pf-matches-store", "data"),
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
    df["m"] = df["MatchMinute"].astype(str).str.extract(r"(\d+)").fillna("0").astype(int)

    colors_db = load_team_colors_db()
    hc, ac = pick_colors(row["HomeName"], row["AwayName"], colors_db)
    colors = {row["HomeName"]: hc, row["AwayName"]: ac}

    fig1 = px.histogram(
        df, x="m", color="TeamName", nbins=40,
        color_discrete_map=colors, barmode="overlay",
        labels={"m": "Minute", "count": "Events"},
    )
    fig1.update_layout(
        title=f"Attacking Events per minute — {row['MatchName']} ({row.get('KickoffDateOnly','')})",
        legend_title="Team",
    )

    fig2 = px.histogram(
        df, x="Description", color="TeamName",
        color_discrete_map=colors, barmode="group",
    )
    fig2.update_layout(title="Attacking Event distribution (Attempt vs Goal)",
                       legend_title="Team")

    return (
        fig1,
        fig2,
        df[["TeamName", "Description", "MatchMinute", "PlayerName"]].fillna("").to_dict("records"),
    )


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
