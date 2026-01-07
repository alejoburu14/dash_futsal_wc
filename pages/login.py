# pages/login.py
import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
from flask_login import current_user
from auth import do_login

dash.register_page(__name__, path="/login", name="Login")

layout = dbc.Container(
    fluid=False,
    className="mt-5",
    children=[
        html.H3("Sign in"),
        dbc.Alert(id="login-alert", is_open=False, color="danger"),
        dbc.Row([
            dbc.Col([
                dbc.Label("Username"),
                dbc.Input(id="login-user", type="text", placeholder="admin"),
                dbc.Label("Password", className="mt-2"),
                dbc.Input(id="login-pass", type="password", placeholder="admin"),
                dbc.Checkbox(id="login-remember", label="Remember me", value=True, className="mt-2"),
                dbc.Button("Sign in", id="login-btn", color="primary", className="mt-3"),
                dcc.Location(id="login-redirect"),
            ], md=5)
        ])
    ]
)

@callback(
    Output("login-alert", "children"),
    Output("login-alert", "is_open"),
    Output("login-redirect", "href"),
    Input("login-btn", "n_clicks"),
    State("login-user", "value"),
    State("login-pass", "value"),
    prevent_initial_call=True,
)
def do_signin(n, user, pwd):
    if not user or not pwd:
        return "Please enter username and password.", True, no_update
    ok = do_login(user.strip(), pwd)
    if ok:
        return no_update, False, "/"
    else:
        return "Invalid credentials.", True, no_update
