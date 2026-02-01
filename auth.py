# auth.py
# ============================================================================
# Authentication module for user login/logout
# Handles simple credential validation and Flask-Login integration
# ============================================================================

from __future__ import annotations
import os
from flask import request
from flask_login import LoginManager, UserMixin, login_user

# Get admin credentials from environment variables (set in .env file)
# Falls back to "admin"/"admin" if env vars not set (development only)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin")


class SimpleUser(UserMixin):
    """
    Simple user class representing a logged-in user.
    UserMixin provides default implementations for Flask-Login methods.
    """
    def __init__(self, username: str):
        """Initialize a user with a username as their ID."""
        self.id = username


def setup_login(app):
    """
    Initialize Flask-Login for the given Flask app.
    This sets up user session management and protection for routes.
    
    Args:
        app: Flask application instance
        
    Returns:
        LoginManager instance configured for the app
    """
    lm = LoginManager()
    lm.login_view = "login"  # Redirect unauthenticated users to /login page
    lm.init_app(app)  # Register the login manager with the Flask app

    # This callback is called when Flask-Login needs to load a user from session
    @lm.user_loader
    def load_user(user_id: str):
        """
        Load a user object from the user_id stored in the session.
        This is called automatically when a user accesses @login_required routes.
        
        Args:
            user_id: The username of the user
            
        Returns:
            SimpleUser object if user exists, None otherwise
        """
        if user_id == ADMIN_USER:
            return SimpleUser(user_id)
        return None

    return lm


def authenticate(username: str, password: str) -> bool:
    """
    Verify if provided credentials are correct.
    Currently checks against a single hardcoded admin account.
    
    Args:
        username: Username to validate
        password: Password to validate
        
    Returns:
        True if credentials match, False otherwise
    """
    return (username == ADMIN_USER) and (password == ADMIN_PASS)


def do_login(username: str, password: str) -> bool:
    """
    Attempt to log in a user with provided credentials.
    If successful, creates a user session via Flask-Login.
    
    Args:
        username: Username to log in
        password: Password to verify
        
    Returns:
        True if login was successful, False if credentials were invalid
    """
    if authenticate(username, password):
        # Create user session (remember=True means "Remember Me" is enabled)
        login_user(SimpleUser(username), remember=True)
        return True
    return False
