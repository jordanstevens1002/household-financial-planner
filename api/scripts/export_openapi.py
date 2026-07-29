"""Export the FastAPI OpenAPI document deterministically."""

import argparse
import json
import sys
from pathlib import Path

from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", help="Output path, or - for standard output")
    args = parser.parse_args()

    document = json.dumps(
        app.openapi(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    if args.output == "-":
        sys.stdout.write(f"{document}\n")
        return
    Path(args.output).write_text(f"{document}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
