# app.py
from __future__ import annotations
import os
from dotenv import load_dotenv
from flask import Flask, redirect
from flask_login import current_user, login_required, logout_user
from flask_caching import Cache

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc

from auth import setup_login
from components.navbar import navbar

load_dotenv()

# --- Flask server + login ---
server = Flask(__name__)
server.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
login_manager = setup_login(server)

# --- Cache (used in data.py via current_app) ---
cache = Cache(server, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 3600})

# --- Dash app ---
external_stylesheets = [dbc.themes.BOOTSTRAP]  # you can swap theme here
app = dash.Dash(
    __name__,
    use_pages=True,
    server=server,
    suppress_callback_exceptions=True,
    external_stylesheets=external_stylesheets,
    title="Futsal WC (Dash)",
)

# Global layout (nav + page content)
app.layout = dbc.Container(
    fluid=True,
    children=[
        dcc.Location(id="url"),
        navbar(),
        html.Div(dash.page_container, id="page-container", className="mt-3")
    ],
)

# Flask logout endpoint (simple redirect)
@server.route("/logout")
@login_required
def flask_logout():
    logout_user()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
