# components/navbar.py
from __future__ import annotations
import dash_bootstrap_components as dbc
from dash import html, dcc
from flask_login import current_user

def navbar():
    return dbc.Navbar(
        dbc.Container(
            fluid=True,
            children=[
                html.A(
                    dbc.Row([
                        dbc.Col(html.I("🏆", style={"font-size":"1.2rem"})),
                        dbc.Col(dbc.NavbarBrand("Futsal WC (Dash)", className="ms-2")),
                    ], align="center", className="g-0"),
                    href="/",
                    style={"textDecoration":"none"},
                ),
                dbc.Nav(
                    [
                        dbc.NavLink("Home", href="/", active="exact"),
                        dbc.NavLink("Dashboard · Performance", href="/performance", active="exact"),
                        dbc.NavLink("Dashboard · Medical", href="/medical", active="exact"),
                    ],
                    className="ms-auto",
                    pills=True,
                ),
                dbc.Nav(
                    [
                        dbc.NavLink("Logout", href="/logout", external_link=True),
                    ],
                    className="ms-3",
                ),
                html.Div(
                    f"Signed in as {current_user.get_id() or '-'}",
                    className="text-muted ms-3",
                )
            ],
        ),
        color="light",
        light=True,
        className="mb-2 border-bottom",
    )
