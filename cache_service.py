"""
Cache Service - In-memory cache for Minecraft server data.

This service stores the latest snapshot of server data in memory so that:
1. API endpoints can return instantly without waiting for RCON calls
2. Multiple dashboards don't spam the Minecraft server with RCON requests
3. Users still see last known good data even if RCON temporarily fails

The cache is updated by a background task that polls RCON every 10 seconds.
"""

from datetime import datetime, timezone
from typing import Optional


class CacheService:
    """
    Simple in-memory cache for Minecraft server status.

    This is a singleton - only one cache exists for the entire application.
    The background polling task writes to it, API endpoints read from it.
    """

    def __init__(self):
        """Initialize cache with empty/default values."""
        # The main cache dictionary - easily extendable with new fields
        self._cache = {
            "online": False,
            "players": {
                "current": [],
                "count": 0,
                "max": 0,
            },
            "performance": {
                "tps": 0.0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "cpu_percent": 0.0,
                "disk_used_gb": 0.0,
                "disk_total_gb": 0.0,
            },
            "uptime_seconds": 0,
            "last_updated": None,  # datetime of last successful update
            "last_error": None,  # error message if last poll failed
        }

    def update(
        self,
        online: bool,
        players_current: list[str],
        players_max: int,
        tps: float = 0.0,
        memory_used_mb: int = 0,
        memory_total_mb: int = 0,
        cpu_percent: float = 0.0,
        disk_used_gb: float = 0.0,
        disk_total_gb: float = 0.0,
        uptime_seconds: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """
        Update the cache with fresh data from RCON and SSH.

        This is called by the background polling task every 5 seconds.

        Args:
            online: Whether server is reachable via RCON
            players_current: List of current player names
            players_max: Maximum players allowed
            tps: Server TPS (ticks per second)
            memory_used_mb: Memory usage in MB
            memory_total_mb: Total memory in MB
            cpu_percent: CPU usage percentage
            disk_used_gb: Disk space used in GB
            disk_total_gb: Total disk space in GB
            uptime_seconds: Server uptime in seconds
            error: Error message if RCON failed, None if successful
        """
        self._cache["online"] = online
        self._cache["players"] = {
            "current": players_current,
            "count": len(players_current),
            "max": players_max,
        }
        self._cache["performance"] = {
            "tps": tps,
            "memory_used_mb": memory_used_mb,
            "memory_total_mb": memory_total_mb,
            "cpu_percent": cpu_percent,
            "disk_used_gb": disk_used_gb,
            "disk_total_gb": disk_total_gb,
        }
        self._cache["uptime_seconds"] = uptime_seconds
        self._cache["last_updated"] = datetime.now(timezone.utc)
        self._cache["last_error"] = error

    def get(self) -> dict:
        """
        Get the current cached data.

        Returns:
            Dictionary with server status, players, performance, timestamps, etc.
            Includes a "stale" flag if data is older than 30 seconds.

        Example:
            {
                "online": True,
                "players": {"current": ["Steve"], "count": 1, "max": 20},
                "performance": {"tps": 19.87, ...},
                "last_updated": "2024-01-15T12:34:56Z",
                "last_error": None,
                "stale": False
            }
        """
        result = self._cache.copy()

        # Add staleness indicator
        # Data is considered "stale" if it's older than 30 seconds
        if result["last_updated"]:
            age_seconds = (datetime.now(timezone.utc) - result["last_updated"]).total_seconds()
            result["stale"] = age_seconds > 30
        else:
            # No data ever cached yet
            result["stale"] = True

        return result

    def get_players(self) -> dict:
        """
        Get just the player data from cache.

        Returns:
            {"current": [...], "count": N, "max": M, "stale": bool}
        """
        data = self.get()
        return {
            "current": data["players"]["current"],
            "count": data["players"]["count"],
            "max": data["players"]["max"],
            "stale": data["stale"],
            "last_updated": data["last_updated"].isoformat() if data["last_updated"] else None,
        }


# Global cache instance
# This is shared across the entire FastAPI application
cache_service = CacheService()
