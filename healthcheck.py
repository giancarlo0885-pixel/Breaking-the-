from __future__ import annotations

import sys

from database import initialize_database, row
from migrations import run_migrations


def main() -> int:
    try:
        initialize_database()
        run_migrations()
        status = row("SELECT * FROM worker_status WHERE id=1")
        print({"ok": True, "database": "connected", "worker_status": status})
        return 0
    except Exception as exc:
        print({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
