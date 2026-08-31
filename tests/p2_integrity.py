"""Read-only inventory. Prints a manifest; never restores or writes business data."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', '.venv', 'node_modules', 'dist', '__pycache__', 'tests'}
EXTENSIONS = {'.xlsx', '.xls', '.csv', '.json', '.ndjson', '.sqlite', '.sqlite3', '.db', '.pdf', '.docx'}


def inventory():
    result = []
    for parent, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(files):
            path = Path(parent) / name
            if path.suffix.lower() in EXTENSIONS:
                result.append(dict(path=path.relative_to(ROOT).as_posix(), size=path.stat().st_size,
                                   sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return sorted(result, key=lambda r: r['path'])


if __name__ == '__main__':
    print(json.dumps(inventory(), ensure_ascii=False, indent=2))
