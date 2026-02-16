"""
RCON Service - Handles communication with the Minecraft server.

RCON (Remote Console) is Minecraft's built-in protocol for sending commands
to the server remotely. It's like typing commands in the server console,
but from Python code.

This service provides a clean interface to:
- Check if the server is online
- Get the list of current players
- (Future) Get server performance metrics
"""

from typing import Optional
from mcrcon import MCRcon
from config import config


class RCONService:
    """
    Service for communicating with Minecraft server via RCON protocol.

    RCON requires:
    1. Server has RCON enabled in server.properties
    2. Correct password
    3. Network access to the server on the RCON port (default 25575)
    """

    def __init__(self):
        """Initialize RCON connection parameters from config."""
        self.host = config.MC_SERVER_HOST
        self.port = config.MC_RCON_PORT
        self.password = config.MC_RCON_PASSWORD

    async def execute_command(self, command: str) -> Optional[str]:
        """
        Execute a command on the Minecraft server via RCON.

        This is the core method - it connects to the server, sends a command,
        and returns the response.

        Args:
            command: The Minecraft command to execute (e.g., "list", "tps")

        Returns:
            The server's response as a string, or None if connection failed.

        Example:
            response = await rcon.execute_command("list")
            # Returns: "There are 3 of a max of 20 players online: Steve, Alex, Herobrine"
        """
        # Call synchronously - this is fine because RCON is only called from
        # the background polling task, not from HTTP request handlers
        # Using run_in_executor causes "signal only works in main thread" errors
        # because mcrcon tries to set up signal handlers in __init__
        return self._execute_sync(command)

    def _execute_sync(self, command: str) -> Optional[str]:
        """
        Synchronous RCON connection and command execution.

        This does the actual RCON connection. It's called from the background
        polling task, so blocking here doesn't affect HTTP request handling.

        How it works:
        1. Opens TCP connection to server on RCON port
        2. Authenticates with password
        3. Sends the command
        4. Receives and returns the response
        5. Closes connection
        """
        try:
            # Context manager automatically handles connection and cleanup
            with MCRcon(self.host, self.password, port=self.port) as mcr:
                response = mcr.command(command)
                return response
        except Exception as e:
            # Log connection errors (server offline, auth failed, network issues, etc.)
            print(f"RCON error: {e}")
            return None

    async def is_server_online(self) -> bool:
        """
        Check if the Minecraft server is online and reachable via RCON.

        Returns:
            True if server responds to RCON, False otherwise.

        This is a quick health check - if we can execute any command, server is online.
        """
        response = await self.execute_command("list")
        return response is not None

    async def get_online_players(self) -> list[str]:
        """
        Get the list of players currently online.

        Returns:
            List of player usernames (e.g., ["Steve", "Alex"])
            Empty list if server is offline or no players online.

        How it works:
        1. Sends "list" command to server
        2. Parses the response to extract player names
        3. Returns them as a Python list

        Example response from server:
        "There are 3 of a max of 20 players online: Steve, Alex, Herobrine"
        """
        response = await self.execute_command("list")

        if not response:
            # Server offline or command failed
            return []

        # Parse the response to extract player names
        # Response format: "There are X of a max of Y players online: Player1, Player2, ..."
        if "online:" in response:
            # Split on "online:" and take the part after it
            players_part = response.split("online:")[1].strip()

            if players_part:
                # Split by comma and strip whitespace from each name
                return [name.strip() for name in players_part.split(",")]

        # No players online or couldn't parse response
        return []

    async def get_max_players(self) -> int:
        """
        Get the maximum number of players allowed on the server.

        Returns:
            Max player count (e.g., 20), or 0 if unavailable.

        Parses the "list" command response to extract the max player count.
        Example: "There are 3 of a max of 20 players online: ..." -> returns 20
        """
        response = await self.execute_command("list")

        if not response:
            return 0

        try:
            # Parse "There are X of a max of Y players online"
            # Split on "max of" and take the number before "players"
            if "max of" in response:
                max_part = response.split("max of")[1].split("players")[0].strip()
                return int(max_part)
        except (ValueError, IndexError):
            # Parsing failed
            pass

        return 0


# Create a global RCON service instance
# This is reused across requests instead of creating new connections each time
rcon_service = RCONService()
