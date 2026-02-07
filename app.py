# app.py
# ============================================================================
# Main application file for Futsal World Cup Dashboard
# This file sets up the Flask server, Dash app, authentication, and caching
# ============================================================================

from __future__ import annotations
import os
from dotenv import load_dotenv
from flask import Flask, redirect
from flask_login import current_user, login_required, logout_user
from flask_caching import Cache

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

from auth import setup_login
from components.navbar import navbar

# Load environment variables from .env file
load_dotenv()

# --- Flask server + login ---
# Create the underlying Flask application (Dash runs on top of Flask)
server = Flask(__name__)
# Set secret key for session management (used for user authentication)
# Falls back to "dev-secret" if SECRET_KEY env var is not set
server.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
# Initialize login manager for Flask-Login (handles user authentication)
login_manager = setup_login(server)

# --- Cache (used in data.py via current_app) ---
# Set up caching to store API responses and avoid repeated requests
# SimpleCache stores data in memory (not persistent across restarts)
# CACHE_DEFAULT_TIMEOUT: cache entries expire after 3600 seconds (1 hour)
cache = Cache(server, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 3600})

# --- Dash app ---
# Load Bootstrap CSS theme for styling (can be swapped with other dbc themes)
external_stylesheets = [dbc.themes.BOOTSTRAP]
# Create the Dash application instance
app = dash.Dash(
    __name__,
    use_pages=True,  # Enable multi-page support (pages/ folder)
    server=server,   # Use the Flask server created above
    suppress_callback_exceptions=True,  # Allows callbacks referencing components not in initial layout
    external_stylesheets=external_stylesheets,
    title="Futsal WC (Dash)",
)

# --- Global layout (navigation bar + page content) ---
# This layout is shown on every page - the navbar is persistent
# dash.page_container will be replaced with different page content based on URL
app.layout = dbc.Container(
    fluid=True,  # Full-width container
    children=[
        dcc.Location(id="url"),  # Tracks the current URL
        navbar(),  # Display navigation bar at top
        # Page content changes based on the URL (handled by use_pages=True)
        html.Div(dash.page_container, id="page-container", className="mt-3")
    ],
)

@callback(
    Output("url", "pathname"),
    Input("logout-btn", "n_clicks"),
    prevent_initial_call=True,
)
def _go_to_logout(n):
    # Clicking the navbar button sends the browser to the Flask endpoint
    return "/logout"

@callback(
    Output("user-label", "children"),
    Input("url", "pathname"),   # fires when you navigate, login, logout (redirect)
    prevent_initial_call=False, # also run once on initial load
)
def _update_user_label(_):
    try:
        from flask_login import current_user
        if getattr(current_user, "is_authenticated", False):
            uid = current_user.get_id() or getattr(current_user, "id", None)
            return f"Signed in as {uid or '-'}"
        return "Signed in as -"
    except Exception:
        return "Signed in as -"


# --- Flask logout endpoint ---
# This endpoint is called when user clicks the "Logout" button
# @login_required decorator ensures only authenticated users can access it
@server.route("/logout")
@login_required
def flask_logout():
    """Handle user logout by clearing session and redirecting to login page."""
    logout_user()  # Clear user session
    return redirect("/login")  # Redirect to login page

# --- Run the application ---
if __name__ == "__main__":
    # debug=True: auto-reload code changes and show detailed error messages
    app.run(debug=True)
