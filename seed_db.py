"""
Seed historical player session data into the SQLite database.

Generates plausible join/leave events distributed across Jan 1 – Apr 20, 2026
that sum to the remembered totals. Also plants a session on Apr 20 (yesterday)
so the "Yesterday's Player Activity" panel shows data right away.

Usage:
    python seed_db.py
"""

import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB_PATH = os.getenv("DB_PATH", "data/minecraft_dashboard.db")
PACIFIC = ZoneInfo("America/Los_Angeles")

# Remembered totals in hours. Players not listed had 0 recorded time.
PLAYER_HOURS = {
    "WooleyRuthless":   141.1,
    "theycallmesalsa":  192.4,
    "LamajioCraft":      45.0,
    "Beaxcel":           11.0,
    "HannieXOXO":       165.3,
    "Raslehc":            3.5,
}

# One guaranteed session per active player on Apr 20 (shows up as "yesterday")
YESTERDAY_SESSIONS = {
    "WooleyRuthless":  2.5,
    "theycallmesalsa": 3.0,
    "HannieXOXO":      2.0,
    "LamajioCraft":    1.5,
}

START_DATE = datetime(2026, 1, 1, tzinfo=PACIFIC)
END_DATE   = datetime(2026, 4, 19, tzinfo=PACIFIC)  # up to Apr 19; Apr 20 handled separately
TOTAL_DAYS = (END_DATE - START_DATE).days

random.seed(42)


def _sessions_for_hours(target_hours: float, exclude_hours: float = 0.0) -> list[float]:
    """Return a list of session durations (in seconds) summing to target_hours."""
    remaining = (target_hours - exclude_hours) * 3600
    if remaining <= 0:
        return []

    avg = random.uniform(1.5 * 3600, 2.5 * 3600)
    n = max(1, round(remaining / avg))

    sessions = []
    for i in range(n):
        if i == n - 1:
            dur = remaining
        else:
            lo = 30 * 60
            hi = min(4 * 3600, remaining - (n - i - 1) * 30 * 60)
            dur = random.uniform(lo, max(lo, hi))
        dur = max(600, dur)
        remaining -= dur
        sessions.append(dur)
        if remaining <= 0:
            break

    return sessions


def _random_evening_start(day_offset: int) -> datetime:
    """Random start time on a given day offset, between 17:00 and 22:30 Pacific."""
    day = START_DATE + timedelta(days=day_offset)
    hour_frac = random.uniform(17.0, 22.5)
    return (day.replace(hour=0, minute=0, second=0, microsecond=0)
            + timedelta(hours=hour_frac)).astimezone(timezone.utc)


def build_events() -> list[tuple]:
    events = []

    for player, hours in PLAYER_HOURS.items():
        yesterday_hours = YESTERDAY_SESSIONS.get(player, 0.0)
        durations = _sessions_for_hours(hours, exclude_hours=yesterday_hours)

        for dur in durations:
            day_offset = random.randint(0, TOTAL_DAYS - 1)
            join_utc = _random_evening_start(day_offset)
            leave_utc = join_utc + timedelta(seconds=dur)
            events.append((player, "join",  join_utc))
            events.append((player, "leave", leave_utc))

        # Guaranteed yesterday session (Apr 20)
        if yesterday_hours > 0:
            apr20 = datetime(2026, 4, 20, 19, 30, 0, tzinfo=PACIFIC).astimezone(timezone.utc)
            events.append((player, "join",  apr20))
            events.append((player, "leave", apr20 + timedelta(hours=yesterday_hours)))

    return events


def seed(db_path: str = DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            event_time  TIMESTAMP NOT NULL,
            UNIQUE(player_name, event_type, event_time)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_player_time ON player_events(player_name, event_time)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON player_events(event_time)")

    events = build_events()
    inserted = 0
    for player, etype, ts in events:
        cur.execute(
            "INSERT OR IGNORE INTO player_events (player_name, event_type, event_time) VALUES (?,?,?)",
            (player, etype, ts.isoformat()),
        )
        inserted += cur.rowcount

    conn.commit()

    # Print verification summary
    print(f"\nInserted {inserted} events ({len(events)} total, {len(events) - inserted} duplicates skipped)\n")
    print(f"{'Player':<22} {'Target':>8} {'Seeded':>8} {'Sessions':>9}")
    print("-" * 52)
    for player, target_hours in sorted(PLAYER_HOURS.items()):
        cur.execute("""
            WITH sessions AS (
                SELECT j.player_name,
                       j.event_time AS joined_at,
                       COALESCE(
                           (SELECT MIN(l.event_time) FROM player_events l
                            WHERE l.player_name = j.player_name
                              AND l.event_type  = 'leave'
                              AND l.event_time  > j.event_time),
                           j.event_time
                       ) AS left_at
                FROM player_events j
                WHERE j.event_type = 'join' AND j.player_name = ?
            )
            SELECT COUNT(*) AS sessions,
                   CAST(SUM((julianday(left_at) - julianday(joined_at)) * 3600 * 24) AS REAL) AS total_seconds
            FROM sessions
        """, (player,))
        row = cur.fetchone()
        actual_hours = (row[1] or 0) / 3600
        print(f"  {player:<20} {target_hours:>7.1f}h {actual_hours:>7.1f}h {row[0]:>9}")

    conn.close()
    print("\nDone. Run 'kubectl cp data/minecraft_dashboard.db <pod>:/app/data/minecraft_dashboard.db' to push to the cluster.")


if __name__ == "__main__":
    seed()
