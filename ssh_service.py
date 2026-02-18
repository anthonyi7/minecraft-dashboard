"""
SSH Service - Remote server metrics collection via SSH.

This service connects to the Minecraft server host via SSH to collect
system-level performance metrics that aren't available via RCON:
- CPU usage of the Java/Minecraft process
- Memory usage (RSS, total system memory)
- Disk usage of the server directory
- TPS (if available in server logs)

Uses paramiko for SSH connections with key-based authentication.
"""

import asyncio
import re
import warnings
from typing import Optional, Dict, Any
import paramiko
from pathlib import Path

from config import config

# Suppress cryptography deprecation warnings from paramiko
# These are for legacy ciphers like TripleDES that are being phased out
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", message=".*TripleDES.*", category=DeprecationWarning)


class SSHService:
    """
    Service for collecting server metrics via SSH.

    Uses the same async pattern as rcon_service and db_service - synchronous
    SSH operations are wrapped with run_in_executor to avoid blocking.
    """

    def __init__(self):
        """Initialize SSH service with configuration from environment."""
        self.host = config.SSH_HOST
        self.port = config.SSH_PORT
        self.username = config.SSH_USER
        self.key_path = config.SSH_KEY_PATH
        self.server_dir = config.MC_SERVER_DIR

        # Cache for Minecraft PID (to avoid repeated lookups)
        self._cached_pid: Optional[int] = None

    async def get_server_metrics(self) -> Dict[str, Any]:
        """
        Get all server performance metrics via SSH.

        Returns:
            Dictionary with CPU, memory, disk, and TPS metrics:
            {
                "cpu_percent": 45.2,
                "memory_used_mb": 4096,
                "memory_total_mb": 8192,
                "memory_percent": 50.0,
                "disk_used_gb": 15.3,
                "disk_total_gb": 50.0,
                "disk_percent": 30.6,
                "tps": 19.8  # May be 0.0 if unavailable
            }
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_server_metrics_sync)

    def _get_server_metrics_sync(self) -> Dict[str, Any]:
        """Synchronous SSH metrics collection."""
        try:
            # Connect via SSH
            ssh = self._create_ssh_client()

            # Get Minecraft process PID
            pid = self._get_minecraft_pid(ssh)

            if pid:
                # Get CPU and memory for the process
                cpu_percent, memory_mb = self._get_process_stats(ssh, pid)
            else:
                print("WARNING: Could not find Minecraft process PID")
                cpu_percent = 0.0
                memory_mb = 0

            # Get total system memory
            memory_total_mb = self._get_total_memory(ssh)

            # Get disk usage
            disk_used_gb, disk_total_gb, disk_percent = self._get_disk_usage(ssh)

            # Try to get TPS from logs (may not be available)
            tps = self._get_tps_from_logs(ssh)

            # Get server uptime
            uptime_seconds = self._get_server_uptime(ssh)

            ssh.close()

            # Calculate memory percentage
            memory_percent = (memory_mb / memory_total_mb * 100) if memory_total_mb > 0 else 0.0

            return {
                "cpu_percent": round(cpu_percent, 1),
                "memory_used_mb": memory_mb,
                "memory_total_mb": memory_total_mb,
                "memory_percent": round(memory_percent, 1),
                "disk_used_gb": round(disk_used_gb, 1),
                "disk_total_gb": round(disk_total_gb, 1),
                "disk_percent": round(disk_percent, 1),
                "tps": round(tps, 2) if tps > 0 else 20.0,  # Default to 20 if unavailable
                "uptime_seconds": uptime_seconds
            }

        except Exception as e:
            print(f"ERROR: SSH metrics collection failed: {e}")
            # Return fallback values
            return {
                "cpu_percent": 0.0,
                "memory_used_mb": 0,
                "memory_total_mb": 0,
                "memory_percent": 0.0,
                "disk_used_gb": 0.0,
                "disk_total_gb": 0.0,
                "disk_percent": 0.0,
                "tps": 20.0,
                "uptime_seconds": 0
            }

    def _create_ssh_client(self) -> paramiko.SSHClient:
        """Create and connect SSH client with key authentication."""
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load private key
        key = paramiko.RSAKey.from_private_key_file(str(Path(self.key_path).expanduser()))

        # Connect
        ssh.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            pkey=key,
            timeout=10
        )

        return ssh

    def _get_minecraft_pid(self, ssh: paramiko.SSHClient) -> Optional[int]:
        """Get the PID of the Minecraft/Java process."""
        # Use cached PID if available (process doesn't restart often)
        if self._cached_pid:
            # Verify it's still running
            _, stdout, _ = ssh.exec_command(f"ps -p {self._cached_pid} -o pid --no-headers")
            if stdout.read().decode().strip():
                return self._cached_pid

        # Find Minecraft process (look for java process with minecraft/forge in command line)
        _, stdout, _ = ssh.exec_command("pgrep -f 'java.*minecraft|java.*forge|java.*neoforge'")
        output = stdout.read().decode().strip()

        if output:
            pid = int(output.split('\n')[0])  # Take first match
            self._cached_pid = pid
            return pid

        return None

    def _get_process_stats(self, ssh: paramiko.SSHClient, pid: int) -> tuple[float, int]:
        """
        Get CPU and memory stats for a specific process.

        Returns:
            (cpu_percent, memory_mb) tuple
        """
        # Use ps to get CPU% and RSS (memory in KB)
        cmd = f"ps -p {pid} -o %cpu,rss --no-headers"
        _, stdout, _ = ssh.exec_command(cmd)
        output = stdout.read().decode().strip()

        if output:
            parts = output.split()
            cpu_percent = float(parts[0])
            memory_kb = int(parts[1])
            memory_mb = memory_kb // 1024
            return cpu_percent, memory_mb

        return 0.0, 0

    def _get_total_memory(self, ssh: paramiko.SSHClient) -> int:
        """Get total system memory in MB."""
        _, stdout, _ = ssh.exec_command("free -m | grep Mem: | awk '{print $2}'")
        output = stdout.read().decode().strip()

        if output:
            return int(output)

        return 0

    def _get_disk_usage(self, ssh: paramiko.SSHClient) -> tuple[float, float, float]:
        """
        Get disk usage for the /mnt/storage mount.

        Returns:
            (used_gb, total_gb, percent) tuple
        """
        cmd = "df -BG /mnt/storage | tail -1"
        _, stdout, _ = ssh.exec_command(cmd)
        output = stdout.read().decode().strip()

        if output:
            # Output format: Filesystem 1G-blocks Used Available Use% Mounted
            # Example: /dev/sda1      50G   15G      33G  31% /
            parts = output.split()
            total_str = parts[1].rstrip('G')
            used_str = parts[2].rstrip('G')
            percent_str = parts[4].rstrip('%')

            total_gb = float(total_str)
            used_gb = float(used_str)
            percent = float(percent_str)

            return used_gb, total_gb, percent

        return 0.0, 0.0, 0.0

    def _get_tps_from_logs(self, ssh: paramiko.SSHClient) -> float:
        """
        Try to get TPS from server logs.

        NeoForge doesn't have a /tps command, but some mods (like Spark)
        output TPS to logs. This is a best-effort attempt.

        Returns:
            TPS value if found, 0.0 otherwise
        """
        log_path = f"{self.server_dir}/logs/latest.log"

        # Look for TPS in recent log lines (last 100 lines)
        cmd = f"tail -100 {log_path} 2>/dev/null | grep -i 'tps\\|tick' | tail -5"
        _, stdout, _ = ssh.exec_command(cmd)
        output = stdout.read().decode().strip()

        if output:
            # Try to parse TPS from common formats
            # Example: "TPS: 19.87" or "Average TPS: 20.0"
            match = re.search(r'tps[:\s]+(\d+\.?\d*)', output, re.IGNORECASE)
            if match:
                return float(match.group(1))

        # TPS not available in logs
        return 0.0

    def _get_server_uptime(self, ssh: paramiko.SSHClient) -> int:
        """
        Get the server's uptime in seconds.

        Returns:
            Uptime in seconds, or 0 if unable to determine
        """
        # Get uptime using /proc/uptime (more accurate than 'uptime' command)
        # Format: "12345.67 98765.43" (uptime_seconds idle_seconds)
        _, stdout, _ = ssh.exec_command("cat /proc/uptime")
        output = stdout.read().decode().strip()

        if output:
            # Take the first number (total uptime in seconds)
            uptime_str = output.split()[0]
            uptime_seconds = int(float(uptime_str))
            return uptime_seconds

        return 0


# Global SSH service instance
ssh_service = SSHService()
