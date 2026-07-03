"""Replay a captured GTA Copilot JSONL state session into the brain listener."""

from __future__ import annotations

import argparse
import socket
import time
from pathlib import Path
from typing import Optional

from .state_listener import HOST, PORT

DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "session-20260702.jsonl"


def replay_file(path: Path, *, host: str = HOST, port: int = PORT, delay_s: float = 0.05) -> int:
    """Send every non-empty line in *path* to the listener as newline-delimited UTF-8."""
    count = 0
    with socket.create_connection((host, port), timeout=10.0) as sock:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.rstrip("\r\n")
                if not line:
                    continue
                sock.sendall((line + "\n").encode("utf-8"))
                count += 1
                if delay_s > 0:
                    time.sleep(delay_s)
    return count


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Replay a captured GTA Copilot state JSONL fixture to the brain listener.")
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--delay", type=float, default=0.05, help="Seconds between lines; use 0 for fastest replay.")
    args = parser.parse_args(argv)
    count = replay_file(args.fixture, host=args.host, port=args.port, delay_s=args.delay)
    print(f"replayed {count} state lines from {args.fixture} to {args.host}:{args.port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
