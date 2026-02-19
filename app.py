"""
Minecraft Dashboard - Main FastAPI Application

This is the backend server that:
1. Serves the static frontend (HTML/CSS/JS)
2. Provides API endpoints for the frontend to fetch data
3. Connects to your Minecraft server via RCON to get real-time data
4. Runs a background task to poll RCON and cache results every 10 seconds
"""

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Import our services
from rcon_service import rcon_service
from cache_service import cache_service
from db_service import db_service
from ssh_service import ssh_service
from stats_service import stats_service
from log_service import log_service

app = FastAPI(title="Minecraft Dashboard")

# CORS middleware for local development
# This allows the frontend to make API calls to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Background Polling Task
# ============================================================================


async def poll_minecraft_server():
    """
    Background task: polls RCON + SSH every 5 seconds for server status/metrics.
    Session tracking is handled separately by poll_logs().
    """
    print("Background polling task started - polling RCON every 5 seconds")

    while True:
        try:
            is_online = await rcon_service.is_server_online()
            current_players = await rcon_service.get_online_players()
            max_players = await rcon_service.get_max_players()
            metrics = await ssh_service.get_server_metrics()

            cache_service.update(
                online=is_online,
                players_current=current_players,
                players_max=max_players,
                tps=metrics["tps"],
                memory_used_mb=metrics["memory_used_mb"],
                memory_total_mb=metrics["memory_total_mb"],
                cpu_percent=metrics["cpu_percent"],
                disk_used_gb=metrics["disk_used_gb"],
                disk_total_gb=metrics["disk_total_gb"],
                uptime_seconds=metrics["uptime_seconds"],
                error=None,
            )

            status = "online" if is_online else "offline"
            print(f"Cache updated: Server {status}, {len(current_players)}/{max_players} players")

        except Exception as e:
            print(f"Polling error: {e}")
            cache_service.update(
                online=False,
                players_current=[],
                players_max=0,
                tps=0.0,
                memory_used_mb=0,
                memory_total_mb=0,
                cpu_percent=0.0,
                disk_used_gb=0.0,
                disk_total_gb=0.0,
                uptime_seconds=0,
                error=str(e),
            )

        await asyncio.sleep(5)


async def poll_logs():
    """
    Background task: tails latest.log every 15 seconds for join/leave events.
    On startup it reads the entire log to backfill today's events.
    """
    print("Log polling task started - tailing server logs every 15 seconds")

    while True:
        try:
            await log_service.poll_logs()
        except Exception as e:
            print(f"Log polling error: {e}")

        await asyncio.sleep(15)


async def poll_stats():
    """
    Background task that refreshes Minecraft statistics every 5 minutes.

    This runs continuously in the background and updates the stats cache with
    player statistics from the Minecraft server's world directory (via SSH):
    - Blocks mined (from stats files)
    - Distance traveled (from stats files)

    Stats update less frequently than online players since they only change
    when players leave or the server saves.
    """
    # Wait 10 seconds on startup to let RCON polling establish first
    await asyncio.sleep(10)
    print("Stats polling task started - refreshing every 5 minutes")

    while True:
        try:
            await stats_service.refresh_stats()
            print("Stats refreshed: Blocks mined and distance traveled updated")
        except Exception as e:
            print(f"Stats polling error: {e}")

        # Wait 5 minutes (300 seconds) before next refresh
        await asyncio.sleep(300)


@app.on_event("startup")
async def startup_event():
    """
    Run when FastAPI application starts up.

    This initializes the database and launches the background polling task
    that will run continuously until the application shuts down.

    Note: on_event is deprecated in newer FastAPI versions in favor of
    lifespan events, but it still works fine and is simpler to understand.
    We can upgrade to the lifespan pattern later if needed.
    """
    await db_service.init_db()
    print("Database initialized")

    asyncio.create_task(poll_minecraft_server())  # RCON/SSH every 5s
    asyncio.create_task(poll_logs())              # Log tailing every 15s
    asyncio.create_task(poll_stats())             # Stats files every 5min


# ============================================================================
# API Endpoints
# ============================================================================


@app.get("/api/healthz")
async def healthz():
    """
    Health check endpoint for the dashboard itself.

    Returns:
        {"ok": True} if the dashboard backend is running.

    Note: This checks if the dashboard is healthy, not the Minecraft server.
    """
    return {"ok": True}


@app.get("/api/players")
async def get_players():
    """
    Get current players online from the Minecraft server.

    NEW in Step 3: This now returns CACHED data instead of making a
    direct RCON call. The background polling task updates the cache
    every 10 seconds.

    Benefits:
    - Instant response (no waiting for RCON)
    - Multiple dashboards don't spam the server
    - Shows last known good data even if RCON temporarily fails

    Returns:
        {
            "current": ["Steve", "Alex"],  # List of player names
            "count": 2,                      # Number of players online
            "max": 20,                       # Max players allowed
            "stale": false,                  # True if data >30s old
            "last_updated": "2024-01-15T12:34:56Z"
        }
    """
    # Simply return cached data - no RCON call in request path!
    return cache_service.get_players()


@app.get("/api/status")
async def status():
    """
    Get overall server status with player info and performance.

    NEW in Step 3: This now returns CACHED data from the background
    polling task instead of making direct RCON calls.

    This is the main endpoint the dashboard uses. It combines:
    - Server online/offline status
    - Player information
    - Performance metrics (still mocked, will be real in future steps)
    - Staleness indicator (true if data >30s old)
    - Last update timestamp

    Returns:
        {
            "online": true/false,
            "players": { ... player data ... },
            "performance": { ... performance data ... },
            "stale": false,
            "last_updated": "2024-01-15T12:34:56Z",
            "last_error": null
        }
    """
    # Simply return cached data - instant response, no RCON wait!
    return cache_service.get()


@app.get("/api/today")
async def get_today_stats():
    """
    Get player activity for today (midnight Pacific time to now).

    Returns player statistics including total playtime, session counts,
    and currently online status for all players seen today.

    Note: Timestamps are stored in UTC, but "today" is calculated based on
    Pacific time (America/Los_Angeles) for display purposes.

    Returns:
        {
            "date": "2024-02-15",
            "timezone": "America/Los_Angeles (Pacific)",
            "players": [
                {
                    "name": "Steve",
                    "total_playtime_seconds": 7200,
                    "total_playtime_formatted": "2h 0m",
                    "session_count": 3,
                    "currently_online": true
                }
            ],
            "summary": {
                "unique_players": 5,
                "total_playtime_seconds": 18000,
                "total_sessions": 12
            }
        }
    """
    return await db_service.get_today_stats()


@app.get("/api/yesterday")
async def get_yesterday_stats():
    """Get player activity for yesterday (midnight-to-midnight Pacific)."""
    return await db_service.get_yesterday_stats()


@app.get("/api/leaderboards")
async def get_leaderboards():
    """
    Get all leaderboard data (top 10 for each metric).

    Combines:
    - Total playtime from session database (all-time)
    - Blocks destroyed from Minecraft stats files
    - Distance traveled from Minecraft stats files

    Returns:
        {
            "playtime": [
                {"name": "Steve", "value": 7200, "formatted": "2h 0m"},
                ...
            ],
            "blocks": [
                {"name": "Alex", "value": 12345, "formatted": "12,345"},
                ...
            ],
            "distance": [
                {"name": "Steve", "value": 5000000, "formatted": "50.0 km"},
                ...
            ],
            "last_updated": "2024-02-15T12:34:56Z",
            "stale": false
        }
    """
    return await stats_service.get_leaderboards()


@app.get("/api/debug/events/{player_name}")
async def debug_player_events(player_name: str):
    """Debug: show raw join/leave events for a player."""
    loop = asyncio.get_event_loop()

    def query():
        import sqlite3
        conn = sqlite3.connect(db_service.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, player_name, event_type, event_time
            FROM player_events
            WHERE LOWER(player_name) = LOWER(?)
            ORDER BY event_time DESC
            LIMIT 100
        """, (player_name,))
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"player_name": player_name, "event_count": len(events), "events": events}

    return await loop.run_in_executor(None, query)


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    """Serve the frontend"""
    return FileResponse("static/index.html")
