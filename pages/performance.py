# pages/performance.py
# ============================================================================
# Performance Dashboard - Match analysis and event tracking
# Displays match information, attacking events, and allows PDF export
# ============================================================================

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

# Register this page in the Dash app
# path="/performance": Performance dashboard URL
dash.register_page(__name__, path="/performance", name="Dashboard · Performance")


# ============================================================================
# Helper Functions for Date Handling
# ============================================================================
def _derive_date_bounds(df_matches: pd.DataFrame) -> tuple[date, date]:
    """
    Extract minimum and maximum dates from match data.
    Used to set date picker bounds.
    
    Args:
        df_matches: DataFrame with match data
        
    Returns:
        Tuple of (min_date, max_date) as Python date objects
    """
    # Return today's date for both if no matches
    if df_matches.empty:
        today = date.today()
        return today, today
    
    # Try to find date column (may be LocalDate or KickoffDate)
    col = "LocalDate" if "LocalDate" in df_matches.columns else "KickoffDate"
    # Convert to date objects (using UTC to avoid timezone issues)
    s = pd.to_datetime(df_matches[col], utc=True, errors="coerce").dt.date
    dmin, dmax = s.min(), s.max()
    
    # Handle case where dates couldn't be parsed
    if pd.isna(dmin) or pd.isna(dmax):
        today = date.today()
        if pd.isna(dmin): dmin = today
        if pd.isna(dmax): dmax = today
    return dmin, dmax


def _with_date_only(df_matches: pd.DataFrame) -> pd.DataFrame:
    """
    Add a KickoffDateOnly column with just date (no time).
    Used for consistent date filtering and display.
    
    Args:
        df_matches: DataFrame with match data
        
    Returns:
        DataFrame with new KickoffDateOnly column
    """
    df = df_matches.copy()
    col = "LocalDate" if "LocalDate" in df.columns else "KickoffDate"
    # Extract just the date part (no time) for consistency
    df["KickoffDateOnly"] = pd.to_datetime(df[col], utc=True, errors="coerce").dt.date
    return df


# ============================================================================
# Filter UI Component
# ============================================================================
def _filters(df_matches: pd.DataFrame):
    """
    Build the filter controls for the performance dashboard.
    Allows filtering by date range, team, and specific match.
    
    Args:
        df_matches: DataFrame with match data
        
    Returns:
        dbc.Card containing filter controls
    """
    # Show warning if no matches found
    if df_matches.empty:
        return html.Div(dbc.Alert("No matches found.", color="warning"))

    # Get date range and list of unique teams
    dmin, dmax = _derive_date_bounds(df_matches)
    teams = sorted(set(df_matches["HomeName"]).union(set(df_matches["AwayName"])))

    return dbc.Card(
        dbc.CardBody([
            dbc.Row([
                # Date range filter
                dbc.Col([
                    dbc.Label("Date range"),
                    dcc.DatePickerRange(
                        id="pf-date-range",
                        min_date_allowed=dmin,
                        max_date_allowed=dmax,
                        start_date=dmin,  # Default to full range
                        end_date=dmax,
                        display_format="YYYY-MM-DD",
                        persistence=True,  # Remember selection between sessions
                        persistence_type="session",
                    ),
                ], md=4),
                
                # Team filter dropdown
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
                
                # Match dropdown (populated by callback)
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


# ============================================================================
# Page Layout
# ============================================================================
def layout():
    """
    Build and return the performance dashboard layout.
    Checks authentication and loads match data.
    
    Returns:
        html.Div: Complete dashboard layout
    """
    # Check if user is logged in
    if not current_user.is_authenticated:
        # Redirect to login page
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    # Load all matches from FIFA API
    df_matches = get_matches()
    # Sort by competition stage, group, and date
    df_matches = sort_matches(df_matches)
    # Add date-only column for consistent filtering
    df_matches = _with_date_only(df_matches)

    # Create empty placeholder figures (prevents undefined titles in UI)
    empty_fig = go.Figure()
    empty_fig.update_layout(title_text="", template="plotly_white")

    return html.Div([
        html.H3("Performance dashboard"),
        
        # Filter controls
        _filters(df_matches),

        # Data stores (invisible components that hold data for callbacks)
        # Stores all match data to avoid re-fetching on every filter change
        dcc.Store(id="pf-matches-store", data=df_matches.to_dict("records")),
        # Stores the currently selected match ID (for state persistence)
        dcc.Store(id="pf-selected-match", storage_type="session"),

        # --- Visualizations ---
        # Chart 1: Attacking events timeline
        dcc.Loading(dcc.Graph(id="pf-graph1", figure=empty_fig), type="dot"),
        # Chart 2: Event type distribution
        dcc.Loading(dcc.Graph(id="pf-graph2", figure=empty_fig), type="dot"),

        # PDF export section
        html.Div([
            dbc.Button("Export PDF", id="pf-export", color="secondary"),
            dcc.Download(id="pf-download"),  # Hidden component for file download
        ], className="mt-2"),

        html.Hr(),
        html.H5("Timeline (attacking events only)"),
        
        # Events table (scrollable, shows goals and shot attempts)
        dcc.Loading(
            DataTable(
                id="pf-table",
                # Define columns to display
                columns=[{"name": c, "id": c}
                         for c in ["TeamName", "Description", "MatchMinute", "PlayerName"]],
                page_action="none",  # Use scrollbar instead of pagination
                style_table={"height": "420px", "overflowY": "auto"},  # Fixed height with scroll
                filter_action="native",  # Enable filtering (search)
                sort_action="native",    # Enable column sorting
                style_cell={"padding": "6px", "whiteSpace": "normal"},
                fixed_rows={"headers": True},  # Keep headers visible when scrolling
            ),
            type="dot"  # Show loading spinner
        ),
    ])


# ============================================================================
# Callbacks - Dynamic Updates
# ============================================================================

@callback(
    Output("pf-selected-match", "data"),
    Input("pf-match", "value"),
    prevent_initial_call=True,
)
def _remember_match(match_id):
    """
    Store the selected match ID in session storage.
    This allows the match selection to persist across page reloads.
    
    Args:
        match_id: Currently selected match ID
        
    Returns:
        match_id to store in session
    """
    return match_id


@callback(
    Output("pf-match", "value"),
    Input("pf-match", "options"),
    State("pf-selected-match", "data"),
    prevent_initial_call=False,
)
def _restore_match_value(options, stored_match_id):
    """
    Restore previously selected match if still available.
    This runs when match options change (e.g., after applying filters).
    
    Args:
        options: Current list of available match options
        stored_match_id: Previously selected match ID from session
        
    Returns:
        stored_match_id if it exists in options, otherwise no_update
    """
    if not options:
        return dash.no_update
    if not stored_match_id:
        return dash.no_update
    
    # Check if the stored match ID is still in the available options
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
    """
    Update the available match options based on applied filters.
    This callback triggers whenever date range or team filter changes.
    
    Args:
        data: All match data from store
        start_date: Selected start date
        end_date: Selected end date
        team: Selected team (or None)
        
    Returns:
        List of match options for dropdown
    """
    if not data:
        return []

    df = pd.DataFrame(data)

    # Build a robust date column handling different date formats
    base = None
    if "KickoffDateOnly" in df.columns:
        # Use pre-computed date-only column if available
        base = df["KickoffDateOnly"]
    elif "LocalDate" in df.columns:
        base = df["LocalDate"]
    else:
        # Fallback to KickoffDate
        base = df["KickoffDate"]

    # Convert all dates to Python date objects for consistent comparison
    df["KDO"] = pd.to_datetime(base, utc=True, errors="coerce").dt.date

    # Parse filter dates
    s_date = pd.to_datetime(start_date, errors="coerce").date() if start_date else None
    e_date = pd.to_datetime(end_date, errors="coerce").date() if end_date else None

    # Apply date range filter
    if s_date:
        df = df[df["KDO"] >= s_date]
    if e_date:
        df = df[df["KDO"] <= e_date]
    
    # Apply team filter (match with home OR away team)
    if team:
        df = df[(df["HomeName"] == team) | (df["AwayName"] == team)]

    # Return list of matches with formatted labels
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
    """
    Load and display data for selected match.
    Fetches event data, creates visualizations, and populates table.
    
    Args:
        match_id: Selected match ID
        data: All match data from store
        
    Returns:
        Tuple of (figure1, figure2, table_data_list)
    """
    # Don't update if no match selected
    if not match_id or not data:
        raise dash.exceptions.PreventUpdate

    # Find selected match in data
    dfm = pd.DataFrame(data)
    row = dfm[dfm["MatchId"] == match_id]
    if row.empty:
        return go.Figure(), go.Figure(), []
    row = row.iloc[0]

    # Fetch match events (goals, shots) from FIFA API
    events = get_match_events(str(match_id))
    # Fetch player information for both teams
    squads = get_players_for_teams([row["HomeId"], row["AwayId"]])

    # Create mapping of team IDs to team names
    name_map = {row["HomeId"]: row["HomeName"], row["AwayId"]: row["AwayName"]}
    df = events.copy()
    
    # Add team names to events
    df["TeamName"] = df["TeamId"].map(name_map)
    
    # Add player names to events by merging with squad data
    if not squads.empty:
        df = df.merge(squads[["PlayerId", "PlayerName"]], on="PlayerId", how="left")
    
    # Filter to only attacking events (goals and shot attempts)
    df = df[df["Description"].isin(["Attempt at Goal", "Goal!"])].copy()
    
    # Extract minute number from MatchMinute column (handle various formats)
    df["m"] = df["MatchMinute"].astype(str).str.extract(r"(\d+)").fillna("0").astype(int)

    # Load team colors from database (for visualization)
    colors_db = load_team_colors_db()
    hc, ac = pick_colors(row["HomeName"], row["AwayName"], colors_db)
    colors = {row["HomeName"]: hc, row["AwayName"]: ac}

    # --- Chart 1: Timeline of attacking events ---
    # Histogram showing when goals and shots occurred
    fig1 = px.histogram(
        df, 
        x="m",                                  # X-axis: Match minute
        color="TeamName",                       # Color by team
        nbins=40,                               # 40 bins (roughly 2 min each)
        color_discrete_map=colors,              # Use team colors
        barmode="overlay",                      # Overlay bars for comparison
        labels={"m": "Minute", "count": "Events"},
    )
    fig1.update_layout(
        title=f"Attacking Events per minute — {row['MatchName']} ({row.get('KickoffDateOnly','')})",
        legend_title="Team",
    )

    # --- Chart 2: Distribution of event types ---
    # Bar chart comparing goals vs shot attempts
    fig2 = px.histogram(
        df, 
        x="Description",                        # X-axis: Event type (Goal vs Attempt)
        color="TeamName",                       # Color by team
        color_discrete_map=colors,
        barmode="group",                        # Group bars by team
    )
    fig2.update_layout(
        title="Attacking Event distribution (Attempt vs Goal)",
        legend_title="Team"
    )

    # --- Table: All events with details ---
    return (
        fig1,
        fig2,
        # Return table data (replace NaN with empty string for clean display)
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
    """
    Export visualizations as PDF file.
    Converts charts to PNG images and embeds in PDF document.
    
    Args:
        n: Number of export button clicks
        fig1: First chart (Plotly figure)
        fig2: Second chart (Plotly figure)
        
    Returns:
        File download object with PDF content
    """
    import plotly.io as pio
    from reportlab.platypus import SimpleDocTemplate, Image, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet

    # Create PDF in memory (BytesIO buffer)
    buf = io.BytesIO()
    
    # Convert Plotly figures to PNG images
    png1 = pio.to_image(fig1, format="png", scale=2)  # scale=2 for high quality
    png2 = pio.to_image(fig2, format="png", scale=2)

    # Create PDF document
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Build PDF content (title + images)
    story = [
        Paragraph("Performance dashboard — Export", styles["Title"]),
        Spacer(1, 12),
    ]
    
    # Add each chart image to the PDF
    for png in (png1, png2):
        img_buf = io.BytesIO(png)
        story += [
            Image(img_buf, width=500, height=300),
            Spacer(1, 12)
        ]
    
    # Write PDF to buffer
    doc.build(story)
    
    # Return file download (Dash helper function)
    return dcc.send_bytes(lambda x: x.write(buf.getvalue()), filename="performance.pdf")


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
