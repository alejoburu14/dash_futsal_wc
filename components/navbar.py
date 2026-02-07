# components/navbar.py
# ============================================================================
# Navigation bar component
# Displays application header with navigation links and user info
# ============================================================================

from __future__ import annotations
from dash import html
import dash_bootstrap_components as dbc


def _safe_user_label() -> str:
    """
    Safely get the current user's username for display in the navbar.
    Uses try/except to handle cases where Flask-Login context is not available.
    
    Returns:
        String showing current username, or "-" if not logged in / error occurs
    """
    try:
        from flask_login import current_user  # lazy import (imported only when needed)
        u = current_user
        uid = None
        if u is not None:
            # Try to get user ID using get_id() method first, then fallback to id attribute
            uid = u.get_id() if hasattr(u, "get_id") else getattr(u, "id", None)
        return f"Signed in as {uid or '-'}"
    except Exception:
        # If any error occurs (e.g., outside request context), return default message
        return "Signed in as -"


def navbar() -> dbc.Navbar:
    """
    Create and return the navigation bar component.
    The navbar appears at the top of every page and contains:
    - App branding/logo
    - Navigation links
    - User info display
    - Logout button
    
    Returns:
        dbc.Navbar: Bootstrap Navbar component
    """
    return dbc.Navbar(
        dbc.Container(
            [
                # App branding and home link
                dbc.NavbarBrand("Futsal WC", href="/"),
                
                # Navigation links (collapse on mobile)
                dbc.Nav(
                    [
                        # Home page link
                        dbc.NavLink("Home", href="/", active="exact"),
                        # Performance dashboard link
                        dbc.NavLink("Performance", href="/performance", active="exact"),
                        # Medical/injuries dashboard link
                        dbc.NavLink("Medical", href="/medical", active="exact"),
                    ],
                    className="me-auto",  # Push to left (auto margin right)
                    navbar=True,
                ),
                
                # User info display
                html.Span("Signed in as -", id="user-label", className="navbar-text me-3"),
                
                # Logout button
                dbc.Button("Logout", id="logout-btn", color="secondary", n_clicks=0),
            ],
            fluid=True,  # Full-width container
        ),
        color="dark",  # Dark background color
        dark=True,  # Use light text for dark background
        className="mb-4",  # Bottom margin spacing
    )

