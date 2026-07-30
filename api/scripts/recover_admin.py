"""Interactively recover a local administrator from the API container."""

import asyncio
import getpass

from app.accounts.recovery import recover_local_admin
from app.core.config import get_settings
from app.core.database import SessionFactory
from app.core.logging import configure_logging


async def recover(username: str, password: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    async with SessionFactory() as database:
        try:
            user = await recover_local_admin(database, username, password, settings)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    print(
        f"Recovered {user.username}. Existing sessions and reset links were invalidated. "
        "The temporary password must be changed at next login."
    )


def main() -> None:
    username = input("Local username to recover: ").strip()
    password = getpass.getpass("Temporary password (minimum 6 characters): ")
    confirmation = getpass.getpass("Confirm temporary password: ")
    if len(password) < 6:
        raise SystemExit("Temporary password must contain at least 6 characters")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    asyncio.run(recover(username, password))


if __name__ == "__main__":
    main()
