# data.py
# ============================================================================
# Data fetching and processing module
# Handles FIFA API requests, database operations, and data transformations
# ============================================================================

from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Tuple
import os
import sqlite3
import re

import pandas as pd
import requests
from flask import current_app

# ============================================================================
# FIFA API Configuration
# ============================================================================
# FIFA API endpoint for fetching futsal world cup data
BASE_URL = "https://api.fifa.com/api/v3"
# Competition ID for Futsal World Cup
COMPETITIONID = "106"
# Season ID for the specific tournament year
SEASONID = "288439"
# Stage ID for the tournament stage
STAGEID = "288440"
# API language (from .env file, defaults to English)
LANG = os.getenv("FIFA_LANG", "en")

# Create a session with custom headers to avoid being blocked by the API
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119 Safari/537.36"
})


def fifa_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Make an HTTP request to the FIFA API.
    
    Args:
        path: API endpoint path (e.g., "/calendar/matches")
        params: Optional query parameters as dict
        
    Returns:
        Parsed JSON response as dictionary
        
    Raises:
        HTTPError: If the API request fails
    """
    # Construct full URL from base URL and path
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    # Start with language parameter
    qp = {"language": LANG}
    # Merge any additional parameters
    if params:
        qp.update(params)
    # Make GET request with timeout (10s for connect, 20s for read)
    r = _session.get(url, params=qp, timeout=(10, 20))
    r.raise_for_status()  # Raise exception for bad status codes
    return r.json()  # Return parsed JSON


# ============================================================================
# Caching System
# ============================================================================
def cache_memoize(timeout=1800):
    """
    Decorator to cache function results using Flask-Caching.
    Avoids repeated API calls for the same data.
    
    Args:
        timeout: Cache expiration time in seconds (default: 30 minutes)
        
    Returns:
        Decorator function
    """
    def _wrap(fn):
        def _inner(*args, **kwargs):
            # Get the cache from Flask app context
            cache = current_app.extensions.get("cache") or current_app.extensions.get("flask-caching")
            if cache and hasattr(cache, "cache"):
                # Use memoization with timeout
                return cache.cache.memoize(timeout)(fn)(*args, **kwargs)
            elif cache and hasattr(cache, "memoize"):
                return cache.memoize(timeout)(fn)(*args, **kwargs)
            # If no cache available, just call the function normally
            return fn(*args, **kwargs)
        return _inner
    return _wrap


def _desc(lst, default=""):
    """
    Extract description from a list of description objects from FIFA API.
    
    Args:
        lst: List that may contain description dicts (from FIFA API)
        default: Default value if extraction fails
        
    Returns:
        Description string or default value
    """
    if isinstance(lst, list) and lst:
        return str(lst[0].get("Description", default) or default)
    return default


# ============================================================================
# FIFA API Data Functions
# ============================================================================
@cache_memoize(timeout=3600)
def get_matches(season_id: str = SEASONID, count: int = 500) -> pd.DataFrame:
    """
    Fetch all matches for a season from FIFA API.
    Results are cached for 1 hour.
    
    Args:
        season_id: Season ID (default: current season)
        count: Maximum number of matches to retrieve
        
    Returns:
        DataFrame with columns: MatchId, StageName, GroupName, HomeId, HomeName,
                               AwayId, AwayName, KickoffDate, MatchName
    """
    try:
        # Call FIFA API to get match data
        data = fifa_get("/calendar/matches", params={"idSeason": season_id, "count": count})
        out = []
        # Process each match in the response
        for m in (data.get("Results") or []):
            # Extract home and away team info from match data
            home, away = (m.get("Home") or {}), (m.get("Away") or {})
            out.append({
                "MatchId": m.get("IdMatch", ""),
                "StageName": _desc(m.get("StageName")),  # e.g., "Group Stage"
                "GroupName": _desc(m.get("GroupName")),  # e.g., "Group A"
                "HomeId": str(home.get("IdTeam", "")),
                "HomeName": home.get("ShortClubName", "") or home.get("TeamName", ""),
                "AwayId": str(away.get("IdTeam", "")),
                "AwayName": away.get("ShortClubName", "") or away.get("TeamName", ""),
                "KickoffDate": m.get("LocalDate", "") or m.get("Date", ""),
            })
        # Create DataFrame from match list
        df = pd.DataFrame(out)
        # Create a human-readable match name column
        if not df.empty:
            df["MatchName"] = df["HomeName"] + " vs " + df["AwayName"]
        return df
    except Exception as e:
        # Return empty DataFrame if API call fails
        return pd.DataFrame()


@cache_memoize(timeout=1800)
def get_match_events(match_id: str,
                     competition_id: str = COMPETITIONID,
                     season_id: str = SEASONID,
                     stage_id: str = STAGEID) -> pd.DataFrame:
    """
    Fetch events (goals, shots, etc.) for a specific match.
    Results are cached for 30 minutes.
    
    Args:
        match_id: ID of the match
        competition_id: Competition ID
        season_id: Season ID
        stage_id: Stage ID
        
    Returns:
        DataFrame with columns: TeamId, PlayerId, Description, MatchMinute
    """
    try:
        # Call FIFA API for match timeline/events
        data = fifa_get(f"/timelines/{competition_id}/{season_id}/{stage_id}/{match_id}")
        ev = data.get("Event") or []
        # Extract key event information
        return pd.DataFrame({
            "TeamId": [str(e.get("IdTeam","")) for e in ev],
            "PlayerId": [str(e.get("IdPlayer","")) for e in ev],
            "Description": [_desc(e.get("TypeLocalized")) for e in ev],  # Event type (Goal, Shot, etc.)
            "MatchMinute": [e.get("MatchMinute","") for e in ev],  # When in match it happened
        })
    except Exception:
        # Return empty DataFrame if API call fails
        return pd.DataFrame()


@cache_memoize(timeout=86400)
def get_players_for_teams(team_ids: Iterable[str],
                          competition_id: str = COMPETITIONID,
                          season_id: str = SEASONID) -> pd.DataFrame:
    """
    Fetch player information for given teams.
    Results are cached for 24 hours (players don't change often).
    
    Args:
        team_ids: List of team IDs to fetch players for
        competition_id: Competition ID
        season_id: Season ID
        
    Returns:
        DataFrame with columns: TeamId, PlayerId, PlayerName
    """
    rows = []
    # Fetch squad for each team
    for tid in team_ids:
        try:
            # Call FIFA API for team squad
            data = fifa_get(f"/teams/{tid}/squad",
                            params={"idCompetition": competition_id, "idSeason": season_id})
            # Extract player information
            for p in (data.get("Players") or []):
                rows.append({
                    "TeamId": str(p.get("IdTeam", "")),
                    "PlayerId": str(p.get("IdPlayer", "")),
                    "PlayerName": _desc(p.get("ShortName")),  # Player name
                })
        except Exception:
            # Skip this team if API call fails
            pass
    return pd.DataFrame(rows)


# ============================================================================
# Local SQLite Database Functions (Team Colors)
# ============================================================================
def load_team_colors_db(path: str = "assets/team_colors.db") -> pd.DataFrame:
    """
    Load team color information from SQLite database.
    This provides custom colors for visualizations.
    
    Args:
        path: Path to the SQLite database file
        
    Returns:
        DataFrame with columns: name, abbr, home_color, away_color, key_name, key_abbr
        Returns empty DataFrame if file doesn't exist
    """
    # Return empty DataFrame if database doesn't exist
    if not os.path.exists(path):
        return pd.DataFrame(columns=["name","abbr","home_color","away_color"])
    
    # Connect to SQLite database
    con = sqlite3.connect(path)
    try:
        # Read team_colors table from database
        df = pd.read_sql("SELECT name, abbr, home_color, away_color FROM team_colors", con)
    finally:
        con.close()  # Always close the connection
    
    # Ensure all columns are strings (not null)
    for c in ["name","abbr","home_color","away_color"]:
        df[c] = df[c].astype(str)
    
    # Create uppercase versions for case-insensitive lookup
    df["key_name"] = df["name"].str.upper().str.strip()
    df["key_abbr"] = df["abbr"].str.upper().str.strip()
    return df


def pick_colors(home_name: str, away_name: str, df_colors: Optional[pd.DataFrame]) -> Tuple[str, str]:
    """
    Select colors for home and away teams based on their names and team colors DB.
    Ensures the colors are sufficiently different for clear visualization.
    
    Args:
        home_name: Name of home team
        away_name: Name of away team
        df_colors: DataFrame with team color information (from load_team_colors_db)
        
    Returns:
        Tuple of (home_color, away_color) as hex strings
    """
    def _lookup(name: str) -> dict:
        """Look up colors for a team by name."""
        if df_colors is None or df_colors.empty:
            # Return default colors if no database available
            return {"home":"#1f77b4","away":"#2ca02c"}
        # Search for team by name (case-insensitive)
        hit = df_colors[df_colors["key_name"] == str(name).upper().strip()]
        if hit.empty:
            # Return default colors if team not found
            return {"home":"#1f77b4","away":"#2ca02c"}
        row = hit.iloc[0]
        return {"home":row["home_color"], "away":row["away_color"]}
    
    def _similar(c1: str, c2: str) -> bool:
        """Check if two hex colors are too similar (within RGB distance of 90)."""
        import numpy as np
        def rgb(h):
            # Convert hex color to RGB numpy array
            h=h.lstrip("#")
            return np.array([int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)])
        # Calculate Euclidean distance in RGB space
        return (abs(rgb(c1)-rgb(c2)).sum()) < 90

    # Look up colors for both teams
    ph = _lookup(home_name)
    pa = _lookup(away_name)
    hc = ph["home"]  # Home team primary color
    ac = pa["home"]  # Away team primary color
    
    # If colors are too similar, use away team's secondary color instead
    if _similar(hc, ac):
        ac = pa["away"]
    
    return hc, ac


# ============================================================================
# Match Sorting and Filtering Helpers
# ============================================================================
def sort_matches(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sort matches by competition stage, group, and date.
    This groups matches logically (groups first, then knockout rounds).
    
    Args:
        df: DataFrame with match data
        
    Returns:
        Sorted DataFrame
    """
    def _g(s):
        """Extract group letter (A, B, C, etc.) from group name."""
        m = re.search(r"Group\s+([A-Z])", str(s), flags=re.I)
        # Return numeric value (1 for A, 2 for B, etc.), or 999 if no group
        return (ord(m.group(1).upper())-64) if m else 999
    
    def _stage(s):
        """
        Convert tournament stage name to numeric sorting order.
        Earlier stages (groups) get lower numbers.
        """
        s = (s or "").lower()
        # Map stage names to sort order
        order = [
            (r"group", 100),  # Group stage comes first
            (r"round\s*of\s*16|sixteen", 200),  # Round of 16
            (r"quarter", 300),  # Quarterfinals
            (r"semi", 400),  # Semifinals
            (r"third|3rd", 500),  # Third place match
            (r"final", 600),  # Final match
        ]
        for pat,val in order:
            if re.search(pat,s):
                return val
        return 700  # Unknown stage gets highest number
    
    # Return original if empty
    if df.empty:
        return df
    
    # Add temporary columns for sorting, then drop them
    return df.assign(_g=df["GroupName"].map(_g),
                     _s=df["StageName"].map(_stage))\
             .sort_values(by=["_g","_s","KickoffDate","MatchName"])\
             .drop(columns=["_g","_s"])
