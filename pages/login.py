# pages/login.py
# ============================================================================
# Login page for user authentication
# Handles username/password submission and session creation
# ============================================================================

import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from flask_login import current_user
from auth import do_login

# Register this page in the Dash app
# path="/login": This page handles user login
dash.register_page(__name__, path="/login", name="Login")

# Page layout - login form with username, password, and remember me checkbox
layout = dbc.Container(
    fluid=False,
    className="mt-5",
    children=[
        html.H3("Sign in"),
        
        # Alert box for showing error messages
        dbc.Alert(id="login-alert", is_open=False, color="danger"),
        
        dbc.Row([
            dbc.Col([
                # Username input field
                dbc.Label("Username"),
                dbc.Input(id="login-user", type="text", placeholder="admin"),
                
                # Password input field
                dbc.Label("Password", className="mt-2"),
                dbc.Input(id="login-pass", type="password", placeholder="admin"),
                
                # "Remember me" checkbox (for persistent login)
                dbc.Checkbox(id="login-remember", label="Remember me", value=True, className="mt-2"),
                
                # Login button to submit credentials
                dbc.Button("Sign in", id="login-btn", color="primary", className="mt-3"),
                
                # Location component to handle page redirects after login
                dcc.Location(id="login-redirect"),
            ], md=5)
        ])
    ]
)

# Callback: Handle login button click
@callback(
    Output("login-alert", "children"),       # Error message text
    Output("login-alert", "is_open"),        # Show/hide alert
    Output("login-redirect", "href"),        # URL to redirect to after login
    Input("login-btn", "n_clicks"),          # Trigger when button is clicked
    State("login-user", "value"),            # Get current username value
    State("login-pass", "value"),            # Get current password value
    prevent_initial_call=True,               # Don't run on page load
)
def do_signin(n, user, pwd):
    """
    Validate login credentials and either show error or redirect to home.
    
    Args:
        n: Number of button clicks (from n_clicks)
        user: Username entered by user
        pwd: Password entered by user
        
    Returns:
        Tuple of (alert_message, alert_visible, redirect_url)
    """
    # Check if both username and password were entered
    if not user or not pwd:
        # Show error message
        return "Please enter username and password.", True, no_update
    
    # Attempt to log in with provided credentials
    ok = do_login(user.strip(), pwd)
    
    if ok:
        # Login successful - redirect to home page
        return no_update, False, "/"
    else:
        # Login failed - show error message
        return "Invalid credentials.", True, no_update
