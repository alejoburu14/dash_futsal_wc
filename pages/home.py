# pages/home.py
import dash
from dash import html
from flask_login import current_user

dash.register_page(__name__, path="/", name="Home")

def layout():
    if not current_user.is_authenticated:
        return html.Div([html.Meta(httpEquiv="refresh", content="0; url=/login")])
    return html.Div([
        html.H3("Welcome"),
        html.P("This is a basic multi-page Dash app with authentication."),
        html.Ul([
            html.Li("Use the Performance dashboard to explore match timelines."),
            html.Li("Use the Medical dashboard to explore injuries (non-competitive area)."),
        ])
    ])
