"""
Database Service - SQLite persistence for player session tracking.

This service handles all database operations for tracking when players join/leave
the Minecraft server. It uses SQLite with Write-Ahead Logging (WAL) for better
concurrent read/write performance.

Schema:
- player_sessions: Tracks join/leave events with session durations
  - id: Auto-increment primary key
  - player_name: Minecraft username
  - joined_at: UTC timestamp when player joined
  - left_at: NULL if still online, timestamp when they left
  - duration_seconds: Computed session duration
  - created_at: Row insertion timestamp
"""

import asyncio
import os
import sqlite3
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Any
from pathlib import Path

from config import config


class DatabaseService:
    """
    Service for managing SQLite database operations.

    Uses the same async pattern as rcon_service.py - synchronous SQLite calls
    are wrapped with run_in_executor to avoid blocking the event loop.
    """

    def __init__(self, db_path: str = None):
        """Initialize database service with path to SQLite file."""
        self.db_path = db_path or config.DB_PATH

    async def init_db(self) -> None:
        """
        Initialize database: create tables, indexes, and enable WAL mode.

        This should be called on application startup before any polling begins.
        Creates the data directory if it doesn't exist.
        """
        # Ensure data directory exists
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created data directory: {db_dir}")

        # Run initialization in executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._init_db_sync)

        # Close any orphaned sessions (left_at=NULL from previous runs)
        await self.close_orphaned_sessions()

    def _init_db_sync(self) -> None:
        """Synchronous database initialization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Enable WAL mode for better concurrent read/write performance
            cursor.execute("PRAGMA journal_mode=WAL;")

            # Create player_sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    joined_at TIMESTAMP NOT NULL,
                    left_at TIMESTAMP DEFAULT NULL,
                    duration_seconds INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_player_sessions_player_name
                ON player_sessions(player_name)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_player_sessions_joined_at
                ON player_sessions(joined_at)
            """)

            conn.commit()
            conn.close()

            print(f"Database initialized at {self.db_path}")

        except Exception as e:
            print(f"ERROR: Database initialization failed: {e}")
            raise

    async def close_orphaned_sessions(self) -> None:
        """
        Close any orphaned sessions (sessions with left_at=NULL).

        This is called on startup to clean up sessions that were left open from
        previous app runs (e.g., due to app crashes or restarts). We set their
        left_at to their joined_at (0 duration) since we don't know when they
        actually left.

        This prevents orphaned sessions from inflating playtime statistics.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._close_orphaned_sessions_sync)

    def _close_orphaned_sessions_sync(self) -> None:
        """Synchronous orphaned session cleanup."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find all sessions with NULL left_at
            cursor.execute("""
                SELECT id, player_name, joined_at FROM player_sessions
                WHERE left_at IS NULL
            """)

            orphaned = cursor.fetchall()

            if orphaned:
                print(f"Found {len(orphaned)} orphaned session(s) from previous runs:")

                for session_id, player_name, joined_at_str in orphaned:
                    # Parse the joined_at timestamp
                    joined_at = datetime.fromisoformat(joined_at_str.replace('Z', '+00:00'))

                    # Close the session with same time as join (0 duration)
                    # We don't know when they actually left
                    cursor.execute("""
                        UPDATE player_sessions
                        SET left_at = joined_at, duration_seconds = 0
                        WHERE id = ?
                    """, (session_id,))

                    print(f"  - Closed orphaned session for {player_name} (ID: {session_id})")

                conn.commit()
            else:
                print("No orphaned sessions found")

            conn.close()

        except Exception as e:
            print(f"WARNING: Failed to close orphaned sessions: {e}")

    async def record_join(self, player_name: str, timestamp: datetime) -> None:
        """
        Record a player joining the server.

        Inserts a new session row with joined_at timestamp and left_at=NULL
        (indicating the player is currently online).

        Args:
            player_name: Minecraft username
            timestamp: UTC datetime when player joined
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._record_join_sync,
            player_name,
            timestamp
        )

    def _record_join_sync(self, player_name: str, timestamp: datetime) -> None:
        """Synchronous join recording."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO player_sessions (player_name, joined_at, left_at, duration_seconds)
                VALUES (?, ?, NULL, NULL)
            """, (player_name, timestamp))

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"WARNING: Failed to record join for {player_name}: {e}")

    async def record_leave(self, player_name: str, timestamp: datetime) -> None:
        """
        Record a player leaving the server.

        Updates the most recent session for this player (where left_at is NULL)
        by setting left_at timestamp and computing duration_seconds.

        Args:
            player_name: Minecraft username
            timestamp: UTC datetime when player left
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._record_leave_sync,
            player_name,
            timestamp
        )

    def _record_leave_sync(self, player_name: str, timestamp: datetime) -> None:
        """Synchronous leave recording."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find the most recent active session for this player
            cursor.execute("""
                SELECT id, joined_at FROM player_sessions
                WHERE player_name = ? AND left_at IS NULL
                ORDER BY joined_at DESC
                LIMIT 1
            """, (player_name,))

            row = cursor.fetchone()
            if row:
                session_id, joined_at_str = row

                # Parse joined_at timestamp
                joined_at = datetime.fromisoformat(joined_at_str.replace('Z', '+00:00'))

                # Compute duration in seconds
                duration_seconds = int((timestamp - joined_at).total_seconds())

                # Update the session
                cursor.execute("""
                    UPDATE player_sessions
                    SET left_at = ?, duration_seconds = ?
                    WHERE id = ?
                """, (timestamp, duration_seconds, session_id))

                conn.commit()
            else:
                print(f"WARNING: No active session found for {player_name} to close")

            conn.close()

        except Exception as e:
            print(f"WARNING: Failed to record leave for {player_name}: {e}")

    async def get_today_stats(self) -> dict:
        """
        Get player activity statistics for today (midnight Pacific to now).

        Note: Timestamps are stored in UTC but "today" is calculated based on
        Pacific time (America/Los_Angeles) for display purposes.

        Returns:
            Dictionary with today's date (Pacific), per-player stats, and summary:
            {
                "date": "2024-02-15",
                "timezone": "America/Los_Angeles (Pacific)",
                "players": [
                    {
                        "name": "Steve",
                        "total_playtime_seconds": 7200,
                        "total_playtime_formatted": "2h 0m",
                        "session_count": 3,
                        "currently_online": false
                    }
                ],
                "summary": {
                    "unique_players": 5,
                    "total_playtime_seconds": 18000,
                    "total_sessions": 12
                }
            }
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_today_stats_sync)

    def _get_today_stats_sync(self) -> dict:
        """Synchronous today stats query (Pacific time)."""
        try:
            # Calculate "today" based on Pacific time
            pacific_tz = ZoneInfo("America/Los_Angeles")
            now_pacific = datetime.now(pacific_tz)
            today_pacific = now_pacific.date()

            # Get midnight Pacific time (start of day) and convert to UTC
            midnight_pacific = datetime.combine(today_pacific, datetime.min.time()).replace(tzinfo=pacific_tz)
            midnight_utc = midnight_pacific.astimezone(timezone.utc)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Query player stats for today (Pacific time)
            cursor.execute("""
                SELECT
                    player_name,
                    COUNT(*) as session_count,
                    SUM(
                        CASE
                            WHEN left_at IS NULL THEN
                                -- Active session: compute current duration
                                (strftime('%s', 'now') - strftime('%s', joined_at))
                            ELSE
                                -- Completed session: use stored duration
                                duration_seconds
                        END
                    ) as total_playtime_seconds
                FROM player_sessions
                WHERE joined_at >= ?
                GROUP BY player_name
                ORDER BY total_playtime_seconds DESC
            """, (midnight_utc,))

            rows = cursor.fetchall()

            # Also check which players are currently online
            cursor.execute("""
                SELECT DISTINCT player_name
                FROM player_sessions
                WHERE left_at IS NULL
            """)

            currently_online_names = {row[0] for row in cursor.fetchall()}

            conn.close()

            # Format player data
            players = []
            total_playtime = 0
            total_sessions = 0

            for player_name, session_count, playtime_seconds in rows:
                playtime_seconds = int(playtime_seconds) if playtime_seconds else 0
                total_playtime += playtime_seconds
                total_sessions += session_count

                players.append({
                    "name": player_name,
                    "total_playtime_seconds": playtime_seconds,
                    "total_playtime_formatted": self._format_duration(playtime_seconds),
                    "session_count": session_count,
                    "currently_online": player_name in currently_online_names
                })

            return {
                "date": today_pacific.isoformat(),
                "timezone": "America/Los_Angeles (Pacific)",
                "players": players,
                "summary": {
                    "unique_players": len(players),
                    "total_playtime_seconds": total_playtime,
                    "total_sessions": total_sessions
                }
            }

        except Exception as e:
            print(f"ERROR: Failed to get today stats: {e}")
            # Use Pacific time for error response too
            pacific_tz = ZoneInfo("America/Los_Angeles")
            today_pacific = datetime.now(pacific_tz).date()
            return {
                "date": today_pacific.isoformat(),
                "timezone": "America/Los_Angeles (Pacific)",
                "players": [],
                "summary": {
                    "unique_players": 0,
                    "total_playtime_seconds": 0,
                    "total_sessions": 0
                },
                "error": str(e)
            }

    def _format_duration(self, seconds: int) -> str:
        """
        Format duration in seconds to human-readable string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string like "2h 30m" or "45m" or "30s"
        """
        if seconds < 60:
            return f"{seconds}s"

        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"

        hours = minutes // 60
        remaining_minutes = minutes % 60

        if remaining_minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining_minutes}m"


# Global database service instance
# This is shared across the entire FastAPI application
db_service = DatabaseService()
