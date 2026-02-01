# pages/home.py
# ============================================================================
# Home page of the Futsal World Cup Dashboard
# Simple landing page with links to other dashboards
# ============================================================================

import dash
from dash import html
from flask_login import current_user

# Register this page in the Dash app
# path="/": This is the home page (root URL)
# name="Home": Display name in page title
dash.register_page(__name__, path="/", name="Home")


def layout():
    """
    Build and return the home page layout.
    Checks if user is authenticated; redirects to login if not.
    
    Returns:
        html.Div: Page content or login redirect
    """
    # Check if user is logged in
    if not current_user.is_authenticated:
        # Redirect to login page using meta refresh
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])
    
    # Display welcome content for authenticated users
    return html.Div([
        html.H3("Welcome"),
        html.P("This is a basic multi-page Dash app with authentication."),
        html.Ul([
            # Description of Performance dashboard
            html.Li("Use the Performance dashboard to explore match timelines."),
            # Description of Medical dashboard
            html.Li("Use the Medical dashboard to explore injuries."),
        ])
    ])
