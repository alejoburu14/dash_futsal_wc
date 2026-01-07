# data.py
from __future__ import annotations
from typing import Any, Dict, Iterable, Optional, Tuple
import os
import sqlite3
import re

import pandas as pd
import requests
from flask import current_app

# FIFA API constants
BASE_URL = "https://api.fifa.com/api/v3"
COMPETITIONID = "106"
SEASONID = "288439"
STAGEID = "288440"
LANG = os.getenv("FIFA_LANG", "en")

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119 Safari/537.36"
})

def fifa_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    qp = {"language": LANG}
    if params:
        qp.update(params)
    r = _session.get(url, params=qp, timeout=(10, 20))
    r.raise_for_status()
    return r.json()

# ---- Caching helpers ----
def cache_memoize(timeout=1800):
    """Decorator wrapper using Flask-Caching from app.py"""
    def _wrap(fn):
        def _inner(*args, **kwargs):
            cache = current_app.extensions.get("cache") or current_app.extensions.get("flask-caching")
            if cache and hasattr(cache, "cache"):
                # Flask-Caching stores the Cache at .cache in newer versions
                return cache.cache.memoize(timeout)(fn)(*args, **kwargs)
            elif cache and hasattr(cache, "memoize"):
                return cache.memoize(timeout)(fn)(*args, **kwargs)
            # if no cache registered, just call
            return fn(*args, **kwargs)
        return _inner
    return _wrap

def _desc(lst, default=""):
    if isinstance(lst, list) and lst:
        return str(lst[0].get("Description", default) or default)
    return default

@cache_memoize(timeout=3600)
def get_matches(season_id: str = SEASONID, count: int = 500) -> pd.DataFrame:
    try:
        data = fifa_get("/calendar/matches", params={"idSeason": season_id, "count": count})
        out = []
        for m in (data.get("Results") or []):
            home, away = (m.get("Home") or {}), (m.get("Away") or {})
            out.append({
                "MatchId": m.get("IdMatch", ""),
                "StageName": _desc(m.get("StageName")),
                "GroupName": _desc(m.get("GroupName")),
                "HomeId": str(home.get("IdTeam", "")),
                "HomeName": home.get("ShortClubName", "") or home.get("TeamName", ""),
                "AwayId": str(away.get("IdTeam", "")),
                "AwayName": away.get("ShortClubName", "") or away.get("TeamName", ""),
                "KickoffDate": m.get("LocalDate", "") or m.get("Date", ""),
            })
        df = pd.DataFrame(out)
        if not df.empty:
            df["MatchName"] = df["HomeName"] + " vs " + df["AwayName"]
        return df
    except Exception as e:
        return pd.DataFrame()

@cache_memoize(timeout=1800)
def get_match_events(match_id: str,
                     competition_id: str = COMPETITIONID,
                     season_id: str = SEASONID,
                     stage_id: str = STAGEID) -> pd.DataFrame:
    try:
        data = fifa_get(f"/timelines/{competition_id}/{season_id}/{stage_id}/{match_id}")
        ev = data.get("Event") or []
        return pd.DataFrame({
            "TeamId": [str(e.get("IdTeam","")) for e in ev],
            "PlayerId": [str(e.get("IdPlayer","")) for e in ev],
            "Description": [_desc(e.get("TypeLocalized")) for e in ev],
            "MatchMinute": [e.get("MatchMinute","") for e in ev],
        })
    except Exception:
        return pd.DataFrame()

@cache_memoize(timeout=86400)
def get_players_for_teams(team_ids: Iterable[str],
                          competition_id: str = COMPETITIONID,
                          season_id: str = SEASONID) -> pd.DataFrame:
    rows = []
    for tid in team_ids:
        try:
            data = fifa_get(f"/teams/{tid}/squad",
                            params={"idCompetition": competition_id, "idSeason": season_id})
            for p in (data.get("Players") or []):
                rows.append({
                    "TeamId": str(p.get("IdTeam", "")),
                    "PlayerId": str(p.get("IdPlayer", "")),
                    "PlayerName": _desc(p.get("ShortName")),
                })
        except Exception:
            pass
    return pd.DataFrame(rows)

# --- Colors DB (second data source) ---
def load_team_colors_db(path: str = "assets/team_colors.db") -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=["name","abbr","home_color","away_color"])
    con = sqlite3.connect(path)
    try:
        df = pd.read_sql("SELECT name, abbr, home_color, away_color FROM team_colors", con)
    finally:
        con.close()
    for c in ["name","abbr","home_color","away_color"]:
        df[c] = df[c].astype(str)
    df["key_name"] = df["name"].str.upper().str.strip()
    df["key_abbr"] = df["abbr"].str.upper().str.strip()
    return df

def pick_colors(home_name: str, away_name: str, df_colors: Optional[pd.DataFrame]) -> Tuple[str, str]:
    """Home=home_color vs Away=home_color; if similar, fall back to away_color."""
    def _lookup(name: str) -> dict:
        if df_colors is None or df_colors.empty:
            return {"home":"#1f77b4","away":"#2ca02c"}
        hit = df_colors[df_colors["key_name"] == str(name).upper().strip()]
        if hit.empty:
            return {"home":"#1f77b4","away":"#2ca02c"}
        row = hit.iloc[0]
        return {"home":row["home_color"], "away":row["away_color"]}
    def _similar(c1: str, c2: str) -> bool:
        # simple RGB distance
        import numpy as np
        def rgb(h):
            h=h.lstrip("#"); return np.array([int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)])
        return (abs(rgb(c1)-rgb(c2)).sum()) < 90

    ph = _lookup(home_name); pa = _lookup(away_name)
    hc = ph["home"]; ac = pa["home"]
    if _similar(hc, ac): ac = pa["away"]
    return hc, ac

# helpers
def sort_matches(df: pd.DataFrame) -> pd.DataFrame:
    def _g(s): 
        m = re.search(r"Group\s+([A-Z])", str(s), flags=re.I)
        return (ord(m.group(1).upper())-64) if m else 999
    def _stage(s):
        s = (s or "").lower()
        order = [
            (r"group", 100),
            (r"round\s*of\s*16|sixteen", 200),
            (r"quarter", 300),
            (r"semi", 400),
            (r"third|3rd", 500),
            (r"final", 600),
        ]
        for pat,val in order:
            if re.search(pat,s): return val
        return 700
    if df.empty: return df
    return df.assign(_g=df["GroupName"].map(_g),
                     _s=df["StageName"].map(_stage))\
             .sort_values(by=["_g","_s","KickoffDate","MatchName"])\
             .drop(columns=["_g","_s"])
