"""Phase 5a — deterministic action system for GTA Copilot.

Architecture (from PROJECT_STATE.md, binding):
- Intent detection is DETERMINISTIC — the LLM never chooses actions or coords.
- A committed gazetteer (~15–20 named places with x,y) plus keyword/regex
  matching on the transcript ("waypoint to X", "take me to X", "mark X").
- The LLM only phrases the spoken confirmation.
- Brain-side whitelist mirror; every request+ack logged to actions-<date>.jsonl.
- Unmatched or non-whitelisted intents are logged and politely refused, never sent.
- Wire schema (brain → mod):
  {"type":"action","id":<int>,"action":"set_waypoint","params":{"x":<float>,"y":<float>}}
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_LOGS_DIR = Path(__file__).resolve().parent / "logs"

# ---------------------------------------------------------------------------
# Gazetteer — named Los Santos places with GTA V world coordinates
# ---------------------------------------------------------------------------

# All coords are approximate GTA V world X, Y (Z is ground level, handled mod-side).
# Sources: community maps, in-game GPS testing.
GAZETTEER: dict[str, dict[str, float]] = {
    # Airports
    "lsia":                {"x": -1034.0, "y": -2733.0},
    "los santos airport":  {"x": -1034.0, "y": -2733.0},
    "airport":             {"x": -1034.0, "y": -2733.0},

    # Landmarks
    "maze bank tower":     {"x": -75.0,   "y": -818.0},
    "maze bank":           {"x": -75.0,   "y": -818.0},
    "vinewood sign":       {"x": 711.0,   "y": 1198.0},
    "vinewood":            {"x": 711.0,   "y": 1198.0},
    "del perro pier":      {"x": -1850.0, "y": -1231.0},
    "pier":                {"x": -1850.0, "y": -1231.0},
    "mount chiliad":       {"x": 501.0,   "y": 5604.0},
    "chiliad":             {"x": 501.0,   "y": 5604.0},

    # Districts / neighborhoods
    "downtown":            {"x": -266.0,  "y": -960.0},
    "vespucci beach":      {"x": -1377.0, "y": -1505.0},
    "vespucci":            {"x": -1377.0, "y": -1505.0},
    "sandy shores":        {"x": 1392.0,  "y": 3606.0},
    "paleto bay":          {"x": -165.0,  "y": 6429.0},

    # Services
    "hospital":            {"x": 298.0,   "y": -584.0},
    "police station":      {"x": 428.0,   "y": -981.0},
    "police":              {"x": 428.0,   "y": -981.0},
    "los santos customs":  {"x": -347.0,  "y": -133.0},
    "customs":             {"x": -347.0,  "y": -133.0},
    "ammu-nation":         {"x": 252.0,   "y": -50.0},
    "gun shop":            {"x": 252.0,   "y": -50.0},
    "ammunition":          {"x": 252.0,   "y": -50.0},

    # Recreation
    "golf course":         {"x": -1337.0, "y": 59.0},
    "casino":              {"x": 924.0,   "y": 47.0},
    "strip club":          {"x": 128.0,   "y": -1298.0},

    # Notable
    "fort zancudo":        {"x": -2444.0, "y": 3267.0},
    "military base":       {"x": -2444.0, "y": 3267.0},
    "trevor's trailer":    {"x": 1985.0,  "y": 3812.0},
    "michael's house":     {"x": -813.0,  "y": 179.0},
    "franklin's house":    {"x": 7.0,     "y": -1024.0},
}

# Sorted longest-name-first for greedy matching
_PLACE_NAMES_SORTED: list[str] = sorted(GAZETTEER.keys(), key=len, reverse=True)


# ---------------------------------------------------------------------------
# ACTION_WHITELIST.md mirror (Python side)
# ---------------------------------------------------------------------------

WHITELISTED_ACTIONS: set[str] = {"set_waypoint", "spawn_companion", "heal_player"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionRequest:
    """A validated, ready-to-send action request."""
    id: int
    action: str
    params: dict[str, Any]
    place_name: str  # human label for confirmation speech

    def to_wire(self) -> str:
        """Serialize to the newline-JSON wire format for the mod."""
        payload = {
            "type": "action",
            "id": self.id,
            "action": self.action,
            "params": self.params,
        }
        return json.dumps(payload, ensure_ascii=False)


@dataclass(frozen=True)
class ActionAck:
    """Acknowledgement from the mod for a completed action."""
    id: int
    ok: bool
    err: Optional[str] = None


# ---------------------------------------------------------------------------
# Intent matcher — deterministic, no LLM
# ---------------------------------------------------------------------------

# Patterns that trigger waypoint intent (case-insensitive):
#   "waypoint to X", "set a waypoint to X", "mark X", "take me to X",
#   "go to X", "navigate to X", "head to X", "drive to X"
_WAYPOINT_PATTERNS: list[re.Pattern] = [
    re.compile(
        r"(?:set\s+(?:a\s+)?waypoint\s+(?:to|at|for)\s+)(.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:waypoint\s+(?:to|at|for)\s+)(.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:mark\s+)(.+?)(?:\s+on\s+(?:the\s+)?map)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:take\s+(?:me|us)\s+to\s+)(.+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:(?:go|navigate|head|drive)\s+to\s+)(.+)",
        re.IGNORECASE,
    ),
]


class _IDGenerator:
    """Thread-safe auto-incrementing action ID generator."""

    def __init__(self):
        self._lock = threading.Lock()
        self._next = 1

    def next(self) -> int:
        with self._lock:
            val = self._next
            self._next += 1
            return val


_id_gen = _IDGenerator()


def _extract_place(transcript: str) -> Optional[str]:
    """Try to extract a place name from the transcript via waypoint patterns.

    Returns the matched gazetteer key (lowercase) or None.
    """
    for pattern in _WAYPOINT_PATTERNS:
        m = pattern.search(transcript)
        if m:
            raw_place = m.group(1).strip().rstrip(".!?,;:")
            # Try to match against gazetteer (longest match first)
            raw_lower = raw_place.lower()
            for name in _PLACE_NAMES_SORTED:
                if name in raw_lower:
                    return name
            # No gazetteer match for the extracted noun phrase
            return None
    return None


def match_intent(transcript: str) -> Optional[ActionRequest]:
    """Deterministic intent matcher: transcript → Optional[ActionRequest].

    Currently only supports ``set_waypoint``.  Returns None if no action
    intent is detected or if the place isn't in the gazetteer.
    """
    place = _extract_place(transcript)
    if place is None:
        return None

    coords = GAZETTEER[place]
    return ActionRequest(
        id=_id_gen.next(),
        action="set_waypoint",
        params={"x": coords["x"], "y": coords["y"]},
        place_name=place,
    )


def is_action_whitelisted(action: str) -> bool:
    """Check if an action name is in the Python-side whitelist mirror."""
    return action in WHITELISTED_ACTIONS


# ---------------------------------------------------------------------------
# Action logging
# ---------------------------------------------------------------------------

def _today_text() -> str:
    return _dt.datetime.now().strftime("%Y%m%d")


def append_action_log(
    entry: dict[str, Any],
    *,
    logs_dir: Path = DEFAULT_LOGS_DIR,
    date_text: Optional[str] = None,
) -> Path:
    """Append a request+ack entry to actions-<date>.jsonl."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"actions-{date_text or _today_text()}.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


# ---------------------------------------------------------------------------
# Action client — send_line() + ack correlation
# ---------------------------------------------------------------------------

class ActionClient:
    """Sends action requests over a live socket and waits for ack.

    The listener thread owns the TCP connection. It calls
    ``set_connection()`` when a mod connects, and ``clear_connection()``
    on disconnect. ``send_line()`` is thread-safe.

    Ack flow:
    - ``send_action(req)`` sends the wire JSON and blocks up to ``timeout_s``
      for a matching ack.
    - The listener thread calls ``feed_ack(line)`` for every inbound JSON
      line that has an ``"ack"`` key — the client correlates by id.
    """

    def __init__(
        self,
        *,
        timeout_s: float = 3.0,
        logs_dir: Path = DEFAULT_LOGS_DIR,
        on_overlay: Optional[Callable[[str], None]] = None,
    ):
        self._timeout_s = timeout_s
        self._logs_dir = logs_dir
        self._on_overlay = on_overlay

        self._lock = threading.Lock()
        self._conn_file = None  # writable file-like object for the socket
        self._pending: dict[int, threading.Event] = {}
        self._acks: dict[int, ActionAck] = {}

    # -- connection management (called by listener thread) -----------------

    def set_connection(self, conn_file) -> None:
        """Register the writable side of the mod TCP connection."""
        with self._lock:
            self._conn_file = conn_file

    def clear_connection(self) -> None:
        """Unregister the connection (mod disconnected)."""
        with self._lock:
            self._conn_file = None

    # -- send / receive ----------------------------------------------------

    def send_line(self, line: str) -> bool:
        """Write a line to the mod socket. Returns False if disconnected."""
        with self._lock:
            if self._conn_file is None:
                return False
            try:
                self._conn_file.write(line + "\n")
                self._conn_file.flush()
                return True
            except (OSError, BrokenPipeError):
                self._conn_file = None
                return False

    def feed_ack(self, raw_line: str) -> Optional[ActionAck]:
        """Parse an inbound ack line and unblock the waiting sender.

        Called by the listener thread for every inbound JSON line.
        Returns the ActionAck if it was a valid ack, else None.
        """
        try:
            data = json.loads(raw_line)
        except json.JSONDecodeError:
            return None

        if "ack" not in data:
            return None

        ack = ActionAck(
            id=int(data["ack"]),
            ok=bool(data.get("ok", False)),
            err=data.get("err"),
        )

        with self._lock:
            self._acks[ack.id] = ack
            event = self._pending.get(ack.id)
            if event:
                event.set()

        return ack

    def send_action(self, request: ActionRequest) -> Optional[ActionAck]:
        """Send an action request and wait up to timeout_s for the ack.

        Returns the ActionAck on success, or None on timeout/disconnect.
        Logs the request+ack to actions-<date>.jsonl regardless.
        """
        if not is_action_whitelisted(request.action):
            self._log_refused(request, "action not whitelisted")
            return None

        event = threading.Event()
        with self._lock:
            self._pending[request.id] = event

        # Notify overlay: request sent
        if self._on_overlay:
            self._on_overlay(f"→ {request.action}({request.place_name})…")

        wire = request.to_wire()
        sent = self.send_line(wire)

        if not sent:
            self._log_entry(request, None, "disconnected")
            with self._lock:
                self._pending.pop(request.id, None)
            return None

        # Wait for ack
        event.wait(timeout=self._timeout_s)

        with self._lock:
            self._pending.pop(request.id, None)
            ack = self._acks.pop(request.id, None)

        self._log_entry(request, ack, None if ack else "timeout")

        # Notify overlay: ack result
        if self._on_overlay and ack:
            status = "✓ack" if ack.ok else f"✗nack: {ack.err}"
            self._on_overlay(f"→ {request.action}({request.place_name}) {status}")

        return ack

    # -- logging -----------------------------------------------------------

    def _log_entry(
        self,
        request: ActionRequest,
        ack: Optional[ActionAck],
        error: Optional[str],
    ) -> None:
        entry = {
            "t": int(time.time() * 1000),
            "request_id": request.id,
            "action": request.action,
            "params": request.params,
            "place_name": request.place_name,
            "ack_ok": ack.ok if ack else None,
            "ack_err": ack.err if ack else error,
        }
        append_action_log(entry, logs_dir=self._logs_dir)

    def _log_refused(self, request: ActionRequest, reason: str) -> None:
        entry = {
            "t": int(time.time() * 1000),
            "request_id": request.id,
            "action": request.action,
            "params": request.params,
            "place_name": request.place_name,
            "refused": True,
            "reason": reason,
        }
        append_action_log(entry, logs_dir=self._logs_dir)
