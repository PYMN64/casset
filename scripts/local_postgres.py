"""Start a real, local PostgreSQL for development and testing.

Why this exists
---------------
The Constitution (CLAUDE.md §2) requires PostgreSQL in production, but this
machine has no system PostgreSQL and no Docker, and installing either needs
admin rights. `pgserver` ships a complete, self-contained PostgreSQL binary
that runs entirely from the virtualenv as the current user — so dev and CI
can exercise the *same* database engine production runs, instead of
developing on SQLite and discovering Postgres-only bugs after deploy.

That is not hypothetical: two real bugs in this project (`Sum(boolean)` in
creator_studio_view and users_console — CLAUDE.md items #13/#16) worked fine
on SQLite and errored on PostgreSQL. They were only caught by running the
suite against a real Postgres.

Usage
-----
    # Start (idempotent) and print the connection env vars
    python scripts/local_postgres.py start

    # Run the whole Django test suite against real PostgreSQL
    python scripts/local_postgres.py test

    # Stop the server
    python scripts/local_postgres.py stop

The data directory lives at .pgdata/ (gitignored). Deleting it resets the
local database completely.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PGDATA = BASE_DIR / ".pgdata"
DB_NAME = "casset"


def _ensure_timezone_data(pgdata: Path) -> None:
    """Copy IANA tzdata into the bundled Postgres if it's missing.

    pgserver's Windows binary ships without share/postgresql/timezone, and
    Django issues a mandatory `SET TIME ZONE 'UTC'` on every connect — with
    no tzfiles that fails ("invalid value for parameter TimeZone") and
    nothing can connect at all. Git for Windows bundles a complete zoneinfo
    tree we can borrow.

    The target is share/postgresql/timezone specifically: this build's
    sharedir is share/postgresql (that's where postgres.bki and the .sample
    configs live), NOT the sibling share/timezone directory that also ships
    populated and is never consulted. A normal PostgreSQL install (Docker,
    apt, RDS) always has complete tzdata — this only affects pgserver.
    """
    import pgserver

    share = Path(pgserver.__file__).parent / "pginstall" / "share" / "postgresql"
    target = share / "timezone"
    if target.exists() and any(target.iterdir()):
        return

    for source in (Path("C:/Program Files/Git/mingw64/share/zoneinfo"),
                   Path("C:/Program Files (x86)/Git/mingw64/share/zoneinfo"),
                   Path(pgserver.__file__).parent / "pginstall" / "share" / "timezone"):
        if source.exists() and any(source.iterdir()):
            target.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target, dirs_exist_ok=True)
            print(f"Copied timezone data from {source} -> {target}")
            return
    print("WARNING: no IANA timezone data found to copy; connections may fail.")


def start():
    import pgserver

    PGDATA.mkdir(exist_ok=True)
    _ensure_timezone_data(PGDATA)

    db = pgserver.get_server(str(PGDATA), cleanup_mode=None)
    # get_server() creates a 'postgres' database; make sure ours exists too.
    existing = db.psql(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
    if "1 row" not in existing and "(1 row)" not in existing:
        try:
            db.psql(f"CREATE DATABASE {DB_NAME}")
        except Exception as exc:  # already exists is fine
            if "already exists" not in str(exc):
                raise
    return db


def env_for_django(db=None) -> dict:
    """Env vars that point Django at the local Postgres.

    Connection details are parsed from the server's own URI rather than
    assumed: pgserver picks a free TCP port at first init and reuses it, so
    hardcoding one would break as soon as that port was taken.
    """
    from urllib.parse import urlparse

    if db is None:
        db = start()
    parsed = urlparse(db.get_uri(DB_NAME))
    return {
        "DB_ENGINE": "postgresql",
        "DB_NAME": DB_NAME,
        "DB_USER": parsed.username or "postgres",
        "DB_PASSWORD": parsed.password or "",
        "DB_HOST": parsed.hostname or "127.0.0.1",
        "DB_PORT": str(parsed.port or 5432),
        "DB_SSLMODE": "disable",
    }


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "start"

    if command == "stop":
        import pgserver
        pgserver.get_server(str(PGDATA), cleanup_mode="stop")
        print("PostgreSQL stopped.")
        return 0

    db = start()
    print(f"PostgreSQL running. URI: {db.get_uri(DB_NAME)}")

    if command == "start":
        print("\nEnvironment for Django:")
        for key, value in env_for_django(db).items():
            print(f"  {key}={value}")
        return 0

    if command in ("test", "migrate", "check"):
        env = {**os.environ, **env_for_django(db)}
        args = {
            "test": ["manage.py", "test"],
            "migrate": ["manage.py", "migrate"],
            "check": ["manage.py", "check"],
        }[command] + sys.argv[2:]
        return subprocess.call([sys.executable, *args], env=env, cwd=str(BASE_DIR))

    print(f"Unknown command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
