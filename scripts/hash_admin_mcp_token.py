#!/usr/bin/env python3
from __future__ import annotations

import getpass
import hashlib


def main() -> None:
    token = getpass.getpass("Admin MCP token: ").strip()
    if not token:
        raise SystemExit("No token provided.")
    print(hashlib.sha256(token.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
