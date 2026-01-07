# auth.py
from __future__ import annotations
import os
from flask import request
from flask_login import LoginManager, UserMixin, login_user

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin")

class SimpleUser(UserMixin):
    def __init__(self, username: str):
        self.id = username

def setup_login(app):
    lm = LoginManager()
    lm.login_view = "login"
    lm.init_app(app)

    @lm.user_loader
    def load_user(user_id: str):
        if user_id == ADMIN_USER:
            return SimpleUser(user_id)
        return None

    return lm

def authenticate(username: str, password: str) -> bool:
    return (username == ADMIN_USER) and (password == ADMIN_PASS)

def do_login(username: str, password: str) -> bool:
    if authenticate(username, password):
        login_user(SimpleUser(username), remember=True)
        return True
    return False
