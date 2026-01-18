# components/navbar.py
from __future__ import annotations
from dash import html
import dash_bootstrap_components as dbc

def _safe_user_label() -> str:
    try:
        from flask_login import current_user  # lazy import
        u = current_user
        uid = None
        if u is not None:
            uid = u.get_id() if hasattr(u, "get_id") else getattr(u, "id", None)
        return f"Signed in as {uid or '-'}"
    except Exception:
        return "Signed in as -"

def navbar() -> dbc.Navbar:
    user_text = _safe_user_label()

    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand("Futsal WC", href="/"),
                dbc.Nav(
                    [
                        dbc.NavLink("Home", href="/", active="exact"),
                        dbc.NavLink("Performance", href="/performance", active="exact"),
                        dbc.NavLink("Non-Competitive", href="/medical", active="exact"),
                    ],
                    className="me-auto",
                    navbar=True,
                ),
                # REPLACEMENT for dbc.NavbarText:
                html.Span(user_text, id="user-label", className="navbar-text me-3"),
                dbc.Button("Logout", id="logout-btn", color="secondary", n_clicks=0),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        className="mb-4",
    )

