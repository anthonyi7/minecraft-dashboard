"""
Log Service - Parses Minecraft server logs for player join/leave events.

Reads logs/latest.log from the remote server via SSH.
Tracks file size to only read new bytes on each poll (efficient tail).
On pod restart, re-reads the entire current log to backfill today's events.

Log line formats handled:
  [23:45:12] [Server thread/INFO]: PlayerName joined the game
  [23:45:12] [Server thread/INFO] [minecraft/DedicatedServer]: PlayerName joined the game
  [18Feb2026 19:25:22.581] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: PlayerName joined the game
"""

import re
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import paramiko
from pathlib import Path

from config import config
from db_service import db_service


class LogService:
    # Flexible regex: handles vanilla and modded server log formats.
    # Captures HH:MM:SS and the player name before "joined/left the game".
    # Handles both [HH:MM:SS] and [DDMonYYYY HH:MM:SS.mmm] timestamp formats.
    JOIN_RE = re.compile(
        r'^\[.*?(\d{2}:\d{2}:\d{2})[^\]]*\] \[.*?/INFO\].*?: ([A-Za-z0-9_]{3,16}) joined the game'
    )
    LEAVE_RE = re.compile(
        r'^\[.*?(\d{2}:\d{2}:\d{2})[^\]]*\] \[.*?/INFO\].*?: ([A-Za-z0-9_]{3,16}) left the game'
    )

    def __init__(self):
        self._last_size = 0  # byte offset of last read; 0 = read from start

    async def poll_logs(self) -> None:
        """Read new log lines and insert events into DB."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._poll_logs_sync)

    def _poll_logs_sync(self) -> None:
        try:
            ssh = self._create_ssh_client()
            log_path = f"{config.MC_SERVER_DIR}/logs/latest.log"

            # Get current file size
            _, stdout, _ = ssh.exec_command(f"wc -c < {log_path} 2>/dev/null")
            size_str = stdout.read().decode().strip()
            current_size = int(size_str) if size_str.isdigit() else 0

            if current_size == 0:
                ssh.close()
                return

            if current_size < self._last_size:
                # Log was rotated (server restart), re-read from start
                print("Log rotated — re-reading from beginning")
                self._last_size = 0

            if current_size == self._last_size:
                ssh.close()
                return  # No new content

            # Read only the new bytes (tail -c +N means "skip first N-1 bytes")
            start_byte = self._last_size + 1
            _, stdout, _ = ssh.exec_command(f"tail -c +{start_byte} {log_path}")
            new_content = stdout.read().decode(errors="replace")
            self._last_size = current_size
            ssh.close()

            lines = new_content.splitlines()
            events = self._parse_lines(lines)

            if events:
                inserted = db_service.insert_events_sync(events)
                if inserted > 0:
                    for player, etype, etime in events:
                        print(f"  Log event: {player} {etype} at {etime.strftime('%H:%M:%S UTC')}")

        except Exception as e:
            print(f"ERROR: Log polling failed: {e}")

    def _parse_lines(self, lines: list) -> list:
        """
        Parse log lines into (player_name, event_type, event_time) tuples.

        Uses current UTC time as the reference for resolving HH:MM:SS to a
        full timestamp. Handles midnight edge case: if the log time is more
        than 1 hour in the future, it was written yesterday.
        """
        events = []
        now = datetime.now(timezone.utc)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            m = self.JOIN_RE.match(line)
            if m:
                events.append((m.group(2), "join", self._resolve_time(m.group(1), now)))
                continue

            m = self.LEAVE_RE.match(line)
            if m:
                events.append((m.group(2), "leave", self._resolve_time(m.group(1), now)))

        return events

    def _resolve_time(self, time_str: str, reference: datetime) -> datetime:
        """
        Convert HH:MM:SS to a full UTC datetime using reference as the date.
        If the result is more than 1 hour in the future, assume it's from yesterday.
        """
        h, m, s = map(int, time_str.split(":"))
        today = reference.date()
        event_time = datetime(today.year, today.month, today.day, h, m, s, tzinfo=timezone.utc)

        if event_time > reference + timedelta(hours=1):
            event_time -= timedelta(days=1)

        return event_time

    def _create_ssh_client(self) -> paramiko.SSHClient:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        key = paramiko.RSAKey.from_private_key_file(
            str(Path(config.SSH_KEY_PATH).expanduser())
        )
        ssh.connect(
            hostname=config.SSH_HOST,
            port=config.SSH_PORT,
            username=config.SSH_USER,
            pkey=key,
            timeout=10,
        )
        return ssh


# Global log service instance
log_service = LogService()
