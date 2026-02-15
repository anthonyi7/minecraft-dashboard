"""
Configuration management for the Minecraft Dashboard.

This module loads sensitive configuration (like RCON passwords) from environment variables.
The .env file is git-ignored, so your secrets stay local and don't get pushed to GitHub.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
# This reads the .env file and makes those values available via os.getenv()
load_dotenv()


class Config:
    """
    Configuration settings loaded from environment variables.

    If you need to change these values, edit the .env file, not this file.
    """

    # Minecraft server connection details
    MC_SERVER_HOST: str = os.getenv("MC_SERVER_HOST", "localhost")
    MC_RCON_PORT: int = int(os.getenv("MC_RCON_PORT", "25575"))
    MC_RCON_PASSWORD: str = os.getenv("MC_RCON_PASSWORD", "")

    @classmethod
    def validate(cls) -> None:
        """
        Check that required configuration is present.
        Raises an error if RCON password is not set.
        """
        if not cls.MC_RCON_PASSWORD or cls.MC_RCON_PASSWORD == "changeme":
            raise ValueError(
                "MC_RCON_PASSWORD not set! Please edit .env file with your RCON password."
            )


# Create a global config instance
config = Config()
