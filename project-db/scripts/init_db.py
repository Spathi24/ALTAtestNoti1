"""One-shot DB init helper.

Equivalent to: python -m project_db.cli init-db
"""
from project_db.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["init-db"]))
