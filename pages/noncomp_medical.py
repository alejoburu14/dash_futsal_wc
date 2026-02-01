# pages/noncomp_medical.py
# ============================================================================
# Medical Dashboard - Injury tracking and analysis
# Displays injury data with charts and filterable table
# ============================================================================

from __future__ import annotations
import os
import dash
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
from dash.dash_table import DataTable
import plotly.express as px
import pandas as pd
from flask_login import current_user

# Register this page in the Dash app
# path="/medical": Medical dashboard URL
dash.register_page(__name__, path="/medical", name="Dashboard · Medical")


# ============================================================================
# Data Loading Function
# ============================================================================
def _load_injuries() -> pd.DataFrame:
    """
    Load injury data from CSV file or use synthetic data if file doesn't exist.
    This allows the app to work even without a real injuries.csv file.
    
    Returns:
        DataFrame with columns: Date, Player, Type, Severity, DaysOut
    """
    path = "assets/injuries.csv"
    if os.path.exists(path):
        # Load real injury data from CSV file
        df = pd.read_csv(path)
    else:
        # Create synthetic sample data for demonstration
        df = pd.DataFrame({
            "Date": pd.date_range("2024-08-01", periods=40, freq="3D"),  # 40 dates, every 3 days
            "Player": [f"Player {i%8 + 1}" for i in range(40)],  # Cycle through 8 players
            "Type": ["Muscle", "Impact", "Overuse", "Joint"] * 10,  # 4 injury types
            "Severity": ["Minor", "Moderate", "Severe", "Minor"] * 10,  # 4 severity levels
            "DaysOut": [3, 10, 21, 5] * 10,  # Days player is unavailable
        })
    
    # Ensure dates are properly formatted
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    # Remove rows with invalid dates
    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    return df


# ============================================================================
# Page Layout
# ============================================================================
def layout():
    """
    Build and return the medical dashboard layout.
    Includes filters, visualizations, and data table.
    
    Returns:
        html.Div: Complete dashboard layout
    """
    # Check if user is logged in
    if not current_user.is_authenticated:
        # Redirect to login page if not authenticated
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])

    # Load injury data
    df = _load_injuries()
    
    # Extract unique values for filter dropdowns
    players = sorted(df["Player"].dropna().unique())  # Sorted list of player names
    types = sorted(df["Type"].dropna().unique())      # Sorted list of injury types
    
    # Determine date range for the date picker
    dmin = df["Date"].min().date() if not df.empty else None  # Earliest injury date
    dmax = df["Date"].max().date() if not df.empty else None  # Latest injury date

    return html.Div([
        html.H3("Medical dashboard"),

        # --- Filter Section ---
        dbc.Card(
            dbc.CardBody([
                dbc.Row([
                    # Date range filter
                    dbc.Col([
                        dbc.Label("Date range"),
                        dcc.DatePickerRange(
                            id="md-dates",
                            start_date=dmin,
                            end_date=dmax,
                            min_date_allowed=dmin,
                            max_date_allowed=dmax,
                            display_format="YYYY-MM-DD",
                            persistence=True,  # Remember selection between sessions
                            persistence_type="session",
                        ),
                    ], md=4),
                    
                    # Player filter dropdown
                    dbc.Col([
                        dbc.Label("Player"),
                        dcc.Dropdown(
                            id="md-player",
                            options=[{"label": p, "value": p} for p in players],
                            placeholder="All",
                            clearable=True,  # Show X button to clear selection
                            persistence=True,
                            persistence_type="session",
                        ),
                    ], md=4),
                    
                    # Injury type filter dropdown
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

        # --- Visualizations (with loading spinners) ---
        # Chart 1: Injury type and severity breakdown
        dcc.Loading(dcc.Graph(id="md-graph1"), type="dot"),
        # Chart 2: Injuries over time trend
        dcc.Loading(dcc.Graph(id="md-graph2"), type="dot"),

        html.Hr(),
        html.H5("Injuries table"),

        # --- Data Table (scrollable, not paginated) ---
        dcc.Loading(
            DataTable(
                id="md-table",
                # Define columns to display
                columns=[{"name": c, "id": c} for c in ["Date", "Player", "Type", "Severity", "DaysOut"]],
                page_action="none",  # Don't paginate - show all rows with scrollbar
                style_table={"height": "420px", "overflowY": "auto"},  # Fixed height with scroll
                filter_action="native",  # Enable filtering (search) in table
                sort_action="native",   # Enable column sorting
                style_cell={"padding": "6px", "whiteSpace": "normal"},  # Cell styling
                fixed_rows={"headers": True},  # Keep header visible when scrolling
            ),
            type="dot",  # Show loading spinner
        ),
    ])


# ============================================================================
# Callback: Update Charts and Table Based on Filters
# ============================================================================
@callback(
    Output("md-graph1", "figure"),     # Output: First chart
    Output("md-graph2", "figure"),     # Output: Second chart
    Output("md-table", "data"),        # Output: Table rows
    Input("md-player", "value"),       # Input: Selected player (or None)
    Input("md-type", "value"),         # Input: Selected injury type (or None)
    Input("md-dates", "start_date"),   # Input: Start date from picker
    Input("md-dates", "end_date"),     # Input: End date from picker
)
def _update_md(player, inj_type, start, end):
    """
    Update visualizations and table when any filter changes.
    This callback is triggered whenever any of the inputs change.
    
    Args:
        player: Selected player name (None = all players)
        inj_type: Selected injury type (None = all types)
        start: Start date from date picker
        end: End date from date picker
        
    Returns:
        Tuple of (figure1, figure2, table_data_list)
    """
    # Load injury data
    df = _load_injuries()

    # --- Apply date filters ---
    if start:
        # Keep only injuries on or after start date
        df = df[df["Date"] >= pd.to_datetime(start)]
    if end:
        # Keep only injuries on or before end date
        df = df[df["Date"] <= pd.to_datetime(end)]

    # --- Apply category filters ---
    if player:
        # Filter to selected player
        df = df[df["Player"] == player]
    if inj_type:
        # Filter to selected injury type
        df = df[df["Type"] == inj_type]

    # --- Chart 1: Histogram of injuries by type and severity ---
    # Shows count of injuries grouped by injury type and severity level
    fig1 = px.histogram(
        df, 
        x="Type",                        # X-axis: Injury type
        color="Severity",                # Colors: Severity level
        barmode="group",                 # Grouped bars (not stacked)
        title="Injuries by type & severity"
    )

    # --- Chart 2: Time series of injuries per month ---
    # Shows how injury frequency changes over time
    tmp = df.copy()
    # Convert date to month (e.g., "2024-08") for monthly grouping
    tmp["Month"] = pd.to_datetime(tmp["Date"], errors="coerce").dt.to_period("M").astype(str)
    fig2 = px.histogram(
        tmp, 
        x="Month",                       # X-axis: Month
        color="Type",                    # Colors: Injury type
        barmode="group",
        title="Injuries per month"
    )

    # --- Prepare table data ---
    # Format dates as strings (YYYY-MM-DD) for display
    out = df.copy()
    if not out.empty:
        out["Date"] = out["Date"].dt.strftime("%Y-%m-%d")

    # Return updated figures and table data
    return fig1, fig2, out[["Date", "Player", "Type", "Severity", "DaysOut"]].to_dict("records")
