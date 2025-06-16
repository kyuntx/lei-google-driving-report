# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Application Overview

This is a Flask web application that generates driving reports by integrating with Google Calendar and Google Maps APIs. It's specifically designed for Yupiteru Lei radar detectors (Lei03/Lei03+/Lei04) that have Google Calendar integration capabilities.

## Core Architecture

- **Main Flask App**: `app.py` - Single-file Flask application handling all routes and business logic
- **Templates**: HTML templates using Bootstrap for UI and Jinja2 templating
  - `templates/index.html` - Main form for authentication and report generation
  - `templates/report.html` - Report display with tabular data and CSV download
  - `templates/cache.html` - Cache management interface for viewing/editing geocoding cache

## Key Components

### Authentication Flow
- Google OAuth2 flow using `google_auth_oauthlib.flow.Flow`
- Session-based credential storage
- Routes: `/authorize`, `/oauth2callback`, `/logout`

### Data Processing Pipeline
1. Extract driving events from Google Calendar (events with "距離" in title)
2. Parse distance and fuel efficiency from event titles using regex
3. Convert coordinates to addresses using Google Maps reverse geocoding with intelligent caching
4. Calculate trip duration and format data for display
5. Export to Shift_JIS CSV for Excel compatibility

### Geocoding Cache System
- **Database**: SQLite database (`geocoding_cache.db`) for persistent cache storage
- **Precision**: Coordinates rounded to 4 decimal places (≈11m accuracy) for cache efficiency
- **Cache Functions**: `init_cache_db()`, `get_cached_address()`, `cache_address()`
- **Management Routes**: `/cache`, `/cache/delete/<id>`, `/cache/update/<id>`, `/cache/clear`
- **API Cost Reduction**: Avoids duplicate Google Maps API calls for identical coordinates

### Required External Services
- Google Calendar API (requires `credentials.json` file)
- Google Maps API (API key provided via form input)

## Common Development Commands

```bash
# Run the application in debug mode
python app.py

# The app runs on http://localhost:5000 by default
```

## Dependencies and Setup

The application requires:
- Flask framework with session management
- Google API client libraries (`google-auth`, `google-auth-oauthlib`, `google-api-python-client`)
- Google Maps client (`googlemaps`)
- Date handling (`python-dateutil`)
- SQLite3 and hashlib (standard libraries) for geocoding cache

## Configuration Requirements

1. **credentials.json**: Google OAuth2 credentials file (not in repo)
2. **Google Maps API Key**: Required for reverse geocoding functionality
3. **Secret Key**: Environment variable `SECRET_KEY` (defaults to development key)
4. **Cache Database**: SQLite file `geocoding_cache.db` (auto-created, excluded from git)

## Data Format Expectations

The application expects Google Calendar events with titles containing:
- Pattern: `距離{number}km ({number}km/l)`
- Example: "距離15.2km (12.5km/l)"
- Location coordinates in the event location field

## CSV Output

Exports driving logs in Shift_JIS encoding with columns:
- 出発時刻 (Departure Time)
- 到着時刻 (Arrival Time) 
- 所要時間(分) (Duration in Minutes)
- 出発地 (Origin)
- 到着地 (Destination)
- 移動距離 (Distance)
- 燃費 (Fuel Efficiency)