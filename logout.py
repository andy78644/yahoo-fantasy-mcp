#!/usr/bin/env python3
"""Remove local Yahoo OAuth tokens. Run this to log out."""
from pathlib import Path

TOKEN_FILE = Path.home() / ".yahoo_fantasy_tokens.json"


def main() -> None:
    if not TOKEN_FILE.exists():
        print("No token file found. Already logged out.")
        return

    TOKEN_FILE.unlink()
    print("Logged out. Authenticate again via Claude when ready.")


if __name__ == "__main__":
    main()
