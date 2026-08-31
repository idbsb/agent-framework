"""Explicit SQLite online backup; never overwrite an existing backup or the source."""
import argparse
import json
import sqlite3
from pathlib import Path


def backup_database(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError("Backup destination must be a new file")
    reader = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=10)
    try:
        if reader.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Source database integrity check failed")
        # Check the expected schema before reserving a new destination.
        reader.execute("SELECT id,payload FROM evidence LIMIT 1").fetchall()
        reader.execute("SELECT kind,id,payload FROM entities LIMIT 1").fetchall()
        with destination.open("xb"):
            pass
        writer = sqlite3.connect(destination)
        try:
            reader.backup(writer)
            if writer.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed")
            return {"evidence_count": writer.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
                    "entity_count": writer.execute("SELECT COUNT(*) FROM entities").fetchone()[0]}
        finally:
            writer.close()
    finally:
        reader.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    print(json.dumps(backup_database(args.source, args.destination)))
