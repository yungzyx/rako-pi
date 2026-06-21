"""Write a sanitized Rako support bundle to JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from config import Settings
from db.database import Database
from product.support_bundle import build_support_bundle, write_support_bundle_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write sanitized Rako support bundle")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args(argv)

    settings = Settings()
    db = Database.open(settings.sqlite_path, settings.sqlite_encryption_key)
    try:
        bundle = build_support_bundle(db, settings)
        output = write_support_bundle_json(bundle, Path(args.output))
    finally:
        db.close()
    print(f"Wrote sanitized support bundle to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
