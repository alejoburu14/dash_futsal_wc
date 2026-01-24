# Futsal WC Dashboard

A modern **Plotly Dash** web application for analyzing Futsal World Cup matches, player performance, and medical/injury data.

## Features

- **🔐 Secure Authentication**: Flask-Login based user management
- **⚽ Performance Dashboard**: Match events, goals, and attempts analysis with interactive visualizations
- **🏥 Medical Dashboard**: Non-competitive injury tracking and statistics
- **📊 Interactive Charts**: Real-time filtering by team, date range, and match selection
- **📥 Data Export**: PDF export functionality for performance reports
- **🎨 Responsive Design**: Bootstrap-based UI with custom styling

## Project Structure

```
dash_futsal_wc/
├── app.py                  # Main Dash app & Flask server
├── auth.py                 # Authentication logic (Flask-Login)
├── data.py                 # FIFA API integration & data fetching
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (SECRET_KEY, credentials)
├── .env.example            # Template for .env
├── assets/
│   └── custom.css          # Custom stylesheets
├── components/
│   └── navbar.py           # Navigation bar component
└── pages/
    ├── home.py             # Home/landing page
    ├── login.py            # Login page
    ├── performance.py       # Performance dashboard
    └── noncomp_medical.py   # Medical/injury dashboard
```

## Installation

### Prerequisites
- Python 3.8+
- pip

### Setup

1. **Clone/download** the repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment** variables:
   ```bash
   cp .env.example .env
   ```
   Then edit `.env` with your settings:
   ```
   SECRET_KEY=your-secret-key-here
   ADMIN_USER=admin
   ADMIN_PASSWORD=admin
   FIFA_LANG=en
   ```

## Running the App

```bash
python app.py
```

Then open your browser to `http://localhost:8050`

### Default Credentials
- **Username**: `admin`
- **Password**: `admin`

(Change these in `.env` before deploying to production)

## Pages Overview

### 🏠 Home (`/`)
Landing page with general information.

### 🔑 Login (`/login`)
User authentication portal. Required to access protected pages.

### ⚽ Performance Dashboard (`/performance`)
Analyze match performance with:
- **Filters**: Date range, team, match selection
- **Charts**: 
  - Events per minute (grouped by team)
  - Event distribution (Attempts vs Goals)
- **Timeline Table**: Attacking actions with player details
- **PDF Export**: Download charts as a PDF report

### 🏥 Medical Dashboard (`/medical`)
Track non-competitive injuries with:
- **Filters**: Player, injury type, date range
- **Charts**:
  - Injuries by type & severity
  - Monthly injury trends
- **Data Table**: Detailed injury records (filterable, sortable)

## Key Technologies

| Component | Technology |
|-----------|-----------|
| **Frontend** | Plotly Dash, Dash Bootstrap Components |
| **Backend** | Flask |
| **Data** | Pandas, FIFA API |
| **Auth** | Flask-Login |
| **Caching** | Flask-Caching |
| **Charts** | Plotly Express |
| **Export** | ReportLab (PDF) |

## Data Sources

1. **FIFA API** (`data.py`):
   - Live match calendars
   - Match events (goals, attempts, etc.)
   - Player squad information

2. **Local Assets**:
   - `assets/injuries.csv` — Injury records (fallback to synthetic data)
   - `assets/team_colors.db` — Team color database (optional)

## Configuration

### Environment Variables (`.env`)
| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | (required) | Flask session encryption |
| `ADMIN_USER` | `admin` | Login username |
| `ADMIN_PASSWORD` | `admin` | Login password |
| `FIFA_LANG` | `en` | API language (e.g., `en`, `es`, `fr`) |

### Caching
The app uses **Flask-Caching** with:
- Match data: **1 hour** cache
- Events: **30 minutes** cache
- Squad data: **24 hours** cache

## File Descriptions

| File | Purpose |
|------|---------|
| [`app.py`](app.py) | Main application entry point; Dash app setup & Flask server |
| [`auth.py`](auth.py) | Login/logout logic and user management |
| [`data.py`](data.py) | FIFA API client, data fetching, and caching |
| [`components/navbar.py`](components/navbar.py) | Reusable navigation component |
| [`pages/home.py`](pages/home.py) | Home page |
| [`pages/login.py`](pages/login.py) | Login form & authentication |
| [`pages/performance.py`](pages/performance.py) | Performance analytics dashboard |
| [`pages/noncomp_medical.py`](pages/noncomp_medical.py) | Medical/injury analytics dashboard |

## Development Notes

- **Pages are auto-registered** via `dash.register_page()` in each page module
- **Callbacks** handle real-time filtering and chart updates
- **Prevent Initial Call**: Some callbacks only trigger on user interaction to reduce API calls
- **Error Handling**: Graceful fallbacks for missing data sources

## Troubleshooting

### "No matches found"
- Check internet connection (FIFA API requires access)
- Verify `SEASONID` and `STAGEID` constants in `data.py` are valid

### Login loop
- Ensure `.env` is loaded with `SECRET_KEY` defined
- Check browser cookies/cache

### Charts not loading
- Check browser console for errors
- Verify data format in CSV/API responses