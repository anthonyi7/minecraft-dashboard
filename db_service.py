"""
Database Service - Event-sourced player session tracking.

Stores raw join/leave events from server logs (append-only).
Sessions and playtime are DERIVED from events on query — never stored explicitly.

Schema:
- player_events: Append-only log of join/leave events
  - player_name: Minecraft username
  - event_type: 'join' or 'leave'
  - event_time: UTC timestamp
  - UNIQUE(player_name, event_type, event_time) prevents duplicates
"""

import asyncio
import os
import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import config


class DatabaseService:

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH

    async def init_db(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._init_db_sync)

    def _init_db_sync(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA journal_mode=WAL;")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_events (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    event_type  TEXT NOT NULL,
                    event_time  TIMESTAMP NOT NULL,
                    UNIQUE(player_name, event_type, event_time)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_player_time
                ON player_events(player_name, event_time)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_time
                ON player_events(event_time)
            """)

            conn.commit()
            conn.close()
            print(f"Database initialized at {self.db_path}")

        except Exception as e:
            print(f"ERROR: Database initialization failed: {e}")
            raise

    def insert_events_sync(self, events: list) -> int:
        """
        Insert a batch of (player_name, event_type, event_time) tuples.
        Silently ignores duplicates (INSERT OR IGNORE).

        Returns the number of new rows inserted.
        """
        if not events:
            return 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            inserted = 0

            for player_name, event_type, event_time in events:
                cursor.execute("""
                    INSERT OR IGNORE INTO player_events (player_name, event_type, event_time)
                    VALUES (?, ?, ?)
                """, (player_name, event_type, event_time.isoformat()))
                inserted += cursor.rowcount

            conn.commit()
            conn.close()
            return inserted

        except Exception as e:
            print(f"ERROR: Failed to insert events: {e}")
            return 0

    async def get_today_stats(self) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_today_stats_sync)

    def _get_today_stats_sync(self) -> dict:
        """
        Derive today's playtime from events.

        For each join event since midnight (Pacific), find the next leave
        for that player. If no leave exists yet, use NOW() — they're still online.
        Sum the resulting session durations per player.
        """
        try:
            pacific_tz = ZoneInfo("America/Los_Angeles")
            now_pacific = datetime.now(pacific_tz)
            today_pacific = now_pacific.date()

            midnight_pacific = datetime.combine(
                today_pacific, datetime.min.time()
            ).replace(tzinfo=pacific_tz)
            midnight_utc = midnight_pacific.astimezone(timezone.utc)

            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # For each join today, find the next leave (or use NOW if still online).
            # julianday arithmetic gives fractional days; multiply by 86400 for seconds.
            cursor.execute("""
                WITH sessions AS (
                    SELECT
                        j.player_name,
                        j.event_time AS joined_at,
                        COALESCE(
                            (SELECT MIN(l.event_time)
                             FROM player_events l
                             WHERE l.player_name = j.player_name
                               AND l.event_type  = 'leave'
                               AND l.event_time  > j.event_time),
                            strftime('%Y-%m-%dT%H:%M:%S', 'now')
                        ) AS left_at
                    FROM player_events j
                    WHERE j.event_type = 'join'
                      AND j.event_time >= ?
                )
                SELECT
                    player_name,
                    COUNT(*) AS session_count,
                    CAST(SUM(
                        (julianday(left_at) - julianday(joined_at)) * 86400
                    ) AS INTEGER) AS total_seconds
                FROM sessions
                GROUP BY player_name
                ORDER BY total_seconds DESC
            """, (midnight_utc.isoformat(),))

            rows = cursor.fetchall()

            # A player is currently online if their most recent event is a join.
            cursor.execute("""
                SELECT player_name
                FROM player_events
                WHERE id IN (
                    SELECT MAX(id) FROM player_events GROUP BY player_name
                )
                AND event_type = 'join'
            """)
            currently_online = {row[0] for row in cursor.fetchall()}

            conn.close()

            players = []
            total_playtime = 0
            total_sessions = 0

            for row in rows:
                seconds = row["total_seconds"] or 0
                total_playtime += seconds
                total_sessions += row["session_count"]
                players.append({
                    "name": row["player_name"],
                    "total_playtime_seconds": seconds,
                    "total_playtime_formatted": self._format_duration(seconds),
                    "session_count": row["session_count"],
                    "currently_online": row["player_name"] in currently_online,
                })

            return {
                "date": today_pacific.isoformat(),
                "timezone": "America/Los_Angeles (Pacific)",
                "players": players,
                "summary": {
                    "unique_players": len(players),
                    "total_playtime_seconds": total_playtime,
                    "total_sessions": total_sessions,
                },
            }

        except Exception as e:
            print(f"ERROR: Failed to get today stats: {e}")
            pacific_tz = ZoneInfo("America/Los_Angeles")
            today_pacific = datetime.now(pacific_tz).date()
            return {
                "date": today_pacific.isoformat(),
                "timezone": "America/Los_Angeles (Pacific)",
                "players": [],
                "summary": {"unique_players": 0, "total_playtime_seconds": 0, "total_sessions": 0},
                "error": str(e),
            }

    def _format_duration(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        remaining = minutes % 60
        return f"{hours}h" if remaining == 0 else f"{hours}h {remaining}m"


# Global database service instance
db_service = DatabaseService()
