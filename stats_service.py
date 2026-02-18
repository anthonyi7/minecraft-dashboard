"""
Stats Service - Minecraft player statistics collection via SSH.

This service reads player statistics from the Minecraft server's world directory:
- usercache.json: Player name → UUID mapping
- world/stats/<uuid>.json: Individual player statistics

Statistics collected:
- Blocks mined (sum of all minecraft:mined values)
- Distance traveled (sum of walk_one_cm, sprint_one_cm, fly_one_cm, swim_one_cm)

Polling strategy:
- Refreshes every 5 minutes (stats change slower than online players)
- Uses in-memory cache for instant API responses
- Combines with session database for total playtime leaderboard
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any
import paramiko
from pathlib import Path

from config import config


class StatsService:
    """
    Service for collecting and caching Minecraft player statistics.

    Uses SSH to read JSON files from the remote Minecraft server.
    """

    def __init__(self):
        """Initialize stats service with empty cache."""
        self._cache = {
            "uuid_mapping": {},  # {"PlayerName": "uuid-string"}
            "player_stats": {},  # {"PlayerName": {"blocks_mined": int, "distance_cm": int}}
            "last_updated": None,
            "stale": True
        }

    async def refresh_stats(self) -> None:
        """
        Refresh player statistics from Minecraft server.

        Steps:
        1. Read usercache.json to get name→UUID mapping
        2. For each UUID, read world/stats/<uuid>.json
        3. Parse blocks mined and distance traveled
        4. Update in-memory cache
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._refresh_stats_sync)

    def _refresh_stats_sync(self) -> None:
        """Synchronous stats refresh via SSH."""
        try:
            # Create SSH connection
            ssh = self._create_ssh_client()

            # Step 1: Read UUID mapping from usercache.json
            uuid_mapping = self._read_usercache_sync(ssh)
            self._cache["uuid_mapping"] = uuid_mapping

            # Step 2: Read stats for each player
            player_stats = {}
            for player_name, uuid in uuid_mapping.items():
                try:
                    stats = self._read_player_stats_sync(ssh, uuid)
                    if stats:  # Only add if file exists and parsed successfully
                        player_stats[player_name] = stats
                except Exception as e:
                    # Skip players with missing/corrupted stats files
                    print(f"WARNING: Failed to read stats for {player_name} ({uuid}): {e}")
                    continue

            self._cache["player_stats"] = player_stats
            self._cache["last_updated"] = datetime.now(timezone.utc)
            self._cache["stale"] = False

            ssh.close()

            print(f"Stats refreshed: {len(player_stats)} players, {len(uuid_mapping)} UUIDs mapped")

        except Exception as e:
            print(f"ERROR: Stats refresh failed: {e}")
            self._cache["stale"] = True

    def _create_ssh_client(self) -> paramiko.SSHClient:
        """Create and connect SSH client with key authentication."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load private key
        key = paramiko.RSAKey.from_private_key_file(str(Path(config.SSH_KEY_PATH).expanduser()))

        # Connect
        ssh.connect(
            hostname=config.SSH_HOST,
            port=config.SSH_PORT,
            username=config.SSH_USER,
            pkey=key,
            timeout=10
        )

        return ssh

    def _read_usercache_sync(self, ssh: paramiko.SSHClient) -> Dict[str, str]:
        """
        Read and parse usercache.json from remote server.

        Returns:
            {"PlayerName": "uuid-string"}
        """
        usercache_path = f"{config.MC_SERVER_DIR}/usercache.json"
        cmd = f"cat {usercache_path}"

        _, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        if error:
            raise Exception(f"Failed to read usercache.json: {error}")

        if not output:
            print("WARNING: usercache.json is empty")
            return {}

        # Parse JSON array
        try:
            usercache = json.loads(output)
            uuid_mapping = {}
            for entry in usercache:
                name = entry.get("name")
                uuid = entry.get("uuid")
                if name and uuid:
                    uuid_mapping[name] = uuid
            return uuid_mapping
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse usercache.json: {e}")

    def _read_player_stats_sync(self, ssh: paramiko.SSHClient, uuid: str) -> Dict[str, int]:
        """
        Read and parse world/stats/<uuid>.json for a specific player.

        Returns:
            {"blocks_mined": int, "distance_cm": int}
            or None if file doesn't exist
        """
        stats_path = f"{config.MC_SERVER_DIR}/world/stats/{uuid}.json"
        cmd = f"cat {stats_path} 2>/dev/null"

        _, stdout, _ = ssh.exec_command(cmd)
        output = stdout.read().decode().strip()

        if not output:
            # Stats file doesn't exist (player never played)
            return None

        # Parse JSON
        try:
            stats_json = json.loads(output)

            # Extract stats
            blocks_mined = self._parse_blocks_mined(stats_json)
            distance_cm = self._parse_distance_traveled(stats_json)
            play_time_seconds = self._parse_play_time(stats_json)

            return {
                "blocks_mined": blocks_mined,
                "distance_cm": distance_cm,
                "play_time_seconds": play_time_seconds
            }
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse stats JSON for {uuid}: {e}")

    def _parse_blocks_mined(self, stats_json: dict) -> int:
        """
        Sum all values in stats["minecraft:mined"].

        Example:
            {"stats": {"minecraft:mined": {"minecraft:stone": 1234, "minecraft:dirt": 567}}}
            Returns: 1801
        """
        try:
            mined = stats_json.get("stats", {}).get("minecraft:mined", {})
            return sum(mined.values())
        except (AttributeError, TypeError):
            return 0

    def _parse_play_time(self, stats_json: dict) -> int:
        """
        Get total playtime from Minecraft's built-in tracking.

        Stored in ticks (20 ticks = 1 second).
        Key: minecraft:play_time (1.17+) or minecraft:play_one_minute (older versions).

        Returns:
            Playtime in seconds
        """
        try:
            custom = stats_json.get("stats", {}).get("minecraft:custom", {})
            ticks = custom.get("minecraft:play_time",
                               custom.get("minecraft:play_one_minute", 0))
            return ticks // 20
        except (AttributeError, TypeError):
            return 0

    def _parse_distance_traveled(self, stats_json: dict) -> int:
        """
        Sum walk_one_cm + sprint_one_cm + fly_one_cm + swim_one_cm.

        Returns distance in centimeters (divide by 100,000 for kilometers).
        """
        try:
            custom = stats_json.get("stats", {}).get("minecraft:custom", {})
            distance = 0
            distance += custom.get("minecraft:walk_one_cm", 0)
            distance += custom.get("minecraft:sprint_one_cm", 0)
            distance += custom.get("minecraft:fly_one_cm", 0)
            distance += custom.get("minecraft:swim_one_cm", 0)
            distance += custom.get("minecraft:climb_one_cm", 0)  # Also include climbing
            return distance
        except (AttributeError, TypeError):
            return 0

    async def get_leaderboards(self) -> Dict[str, Any]:
        """
        Get all leaderboard data (top 10 for each metric).

        All data sourced from Minecraft's own stats files (via SSH).
        Uses minecraft:play_time stat for reliable playtime that persists across pod restarts.

        Returns:
            {
                "playtime": [{"name": str, "value": int, "formatted": str}, ...],
                "blocks": [{"name": str, "value": int, "formatted": str}, ...],
                "distance": [{"name": str, "value": int, "formatted": str}, ...],
                "last_updated": str (ISO timestamp)
            }
        """
        # Get playtime, blocks, and distance from stats cache (all sourced from Minecraft's own files)
        playtime = []
        blocks = []
        distance = []

        for player_name, stats in self._cache["player_stats"].items():
            if stats.get("play_time_seconds", 0) > 0:
                playtime.append({
                    "name": player_name,
                    "value": stats["play_time_seconds"],
                    "formatted": self._format_playtime(stats["play_time_seconds"])
                })
            blocks.append({
                "name": player_name,
                "value": stats["blocks_mined"],
                "formatted": f"{stats['blocks_mined']:,}"
            })
            distance.append({
                "name": player_name,
                "value": stats["distance_cm"],
                "formatted": self._format_distance(stats["distance_cm"])
            })

        # Sort and limit to top 10
        playtime.sort(key=lambda x: x["value"], reverse=True)
        blocks.sort(key=lambda x: x["value"], reverse=True)
        distance.sort(key=lambda x: x["value"], reverse=True)

        playtime = playtime[:10]
        blocks = blocks[:10]
        distance = distance[:10]

        return {
            "playtime": playtime,
            "blocks": blocks,
            "distance": distance,
            "last_updated": self._cache["last_updated"].isoformat() if self._cache["last_updated"] else None,
            "stale": self._cache["stale"]
        }

    def _format_playtime(self, seconds: int) -> str:
        """Format seconds as 'Xh Ym' or 'Xm' or 'Xs'."""
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

    def _format_distance(self, centimeters: int) -> str:
        """Format centimeters as kilometers with 1 decimal place."""
        kilometers = centimeters / 100000
        return f"{kilometers:.1f} km"


# Global stats service instance
stats_service = StatsService()
