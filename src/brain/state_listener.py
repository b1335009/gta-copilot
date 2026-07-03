"""Brain-side TCP listener for GTA Copilot state JSONL."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

HOST = "127.0.0.1"
PORT = 48651
REQUIRED_STATE_KEYS = {"t", "health", "max_health", "armor", "wanted", "pos", "vehicle"}
OPTIONAL_STATE_KEYS = {"companion"}  # Milestone 6: emitted by mod DLLs >= 6a; null or {health, dead}
REQUIRED_POS_KEYS = {"x", "y", "z"}
REQUIRED_VEHICLE_KEYS = {"name", "speed_kmh"}
REQUIRED_COMPANION_KEYS = {"health", "dead"}
DEFAULT_LOGS_DIR = Path(__file__).resolve().parent / "logs"
DEFAULT_OLLAMA_ENDPOINT = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class ModelReply:
    text: str
    fallback: bool
    endpoint: str
    model: str


@dataclass(frozen=True)
class WantedReaction:
    previous_wanted: int
    current_wanted: int
    context: str
    text: str
    fallback: bool
    endpoint: str
    model: str


def parse_state_line(raw_line: str) -> dict[str, Any]:
    try:
        state = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(state, dict):
        raise ValueError("state line must be a JSON object")
    keys = set(state)
    missing = REQUIRED_STATE_KEYS - keys
    unexpected = keys - REQUIRED_STATE_KEYS - OPTIONAL_STATE_KEYS
    if missing:
        raise ValueError(f"missing required keys: {', '.join(sorted(missing))}")
    if unexpected:
        raise ValueError(f"unexpected keys: {', '.join(sorted(unexpected))}")
    pos = state["pos"]
    if not isinstance(pos, dict) or set(pos) != REQUIRED_POS_KEYS:
        raise ValueError("pos must contain exactly x, y, z")
    vehicle = state["vehicle"]
    if vehicle is not None and (not isinstance(vehicle, dict) or set(vehicle) != REQUIRED_VEHICLE_KEYS):
        raise ValueError("vehicle must be null or contain exactly name, speed_kmh")
    companion = state.get("companion")
    if companion is not None and (not isinstance(companion, dict) or set(companion) != REQUIRED_COMPANION_KEYS):
        raise ValueError("companion must be null/absent or contain exactly health, dead")
    return state


def _today_text() -> str:
    return _dt.datetime.now().strftime("%Y%m%d")


def append_raw_line(raw_line: str, *, logs_dir: Path = DEFAULT_LOGS_DIR, date_text: Optional[str] = None) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"state-{date_text or _today_text()}.jsonl"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(raw_line.rstrip("\r\n") + "\n")
    return path


def append_reaction(reaction: WantedReaction, *, logs_dir: Path = DEFAULT_LOGS_DIR, date_text: Optional[str] = None) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"reactions-{date_text or _today_text()}.jsonl"
    payload = {
        "t": int(time.time() * 1000),
        "previous_wanted": reaction.previous_wanted,
        "current_wanted": reaction.current_wanted,
        "context": reaction.context,
        "text": reaction.text,
        "fallback": reaction.fallback,
        "endpoint": reaction.endpoint,
        "model": reaction.model,
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def _pos_text(state: dict[str, Any]) -> str:
    pos = state["pos"]
    return f"{pos['x']:.1f},{pos['y']:.1f},{pos['z']:.1f}"


def describe_vehicle(vehicle: Any) -> str:
    if vehicle is None:
        return "on foot"
    return f"vehicle={vehicle.get('name', 'unknown')}@{vehicle.get('speed_kmh', '?')}km/h"


def format_summary(state: dict[str, Any]) -> str:
    vehicle = state["vehicle"]
    vehicle_text = "on-foot" if vehicle is None else f"{vehicle['name']}@{vehicle['speed_kmh']}km/h"
    companion = state.get("companion")
    if companion is None:
        companion_text = ""
    elif companion["dead"]:
        companion_text = " companion=DEAD"
    else:
        companion_text = f" companion_hp={companion['health']}"
    return (
        f"state t={state['t']} wanted={state['wanted']} "
        f"hp={state['health']}/{state['max_health']} armor={state['armor']} "
        f"vehicle={vehicle_text} pos=({_pos_text(state)}){companion_text}"
    )


def build_wanted_context(previous_wanted: int, current_wanted: int, state: dict[str, Any]) -> str:
    return (
        f"GTA V player wanted {previous_wanted} -> {current_wanted}; "
        f"health {state['health']}/{state['max_health']}; armor {state['armor']}; "
        f"{describe_vehicle(state['vehicle'])}; pos {_pos_text(state)}."
    )


def clean_model_text(text: str) -> str:
    cleaned = " ".join(text.strip().strip('"\'`“”‘’').replace("\r", " ").replace("\n", " ").split())
    for index, char in enumerate(cleaned):
        if char in ".?!":
            return cleaned[: index + 1].strip()
    return cleaned


class OllamaReactionClient:
    def __init__(self, endpoint: Optional[str] = None, model: Optional[str] = None, timeout_s: float = 20.0):
        self.endpoint = (endpoint or os.environ.get("GTA_COPILOT_OLLAMA_ENDPOINT") or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        self.model = model or os.environ.get("GTA_COPILOT_OLLAMA_MODEL") or self._first_available_model() or "<none>"
        self.timeout_s = timeout_s

    def _first_available_model(self) -> Optional[str]:
        try:
            with urllib.request.urlopen(f"{self.endpoint}/api/tags", timeout=2.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return None
        models = payload.get("models") or []
        return models[0].get("name") if models and isinstance(models[0], dict) else None

    def generate_wanted_reaction(self, *, previous_wanted: int, current_wanted: int, context: str) -> ModelReply:
        if self.model == "<none>":
            return self._fallback("no Ollama model is installed")
        prompt = (
            "You are Hermes, a GTA V co-pilot watching live player state. "
            f"Police stars rose from {previous_wanted} to {current_wanted}. "
            f"Player context: {context} "
            "Reply with exactly one urgent sentence under 12 words, second person. "
            "No JSON, no markdown, no explanation."
        )
        body = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 24, "stop": ["\n"]},
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.endpoint}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return self._fallback(f"model endpoint error: {exc}")
        text = clean_model_text(str(payload.get("response") or ""))
        if not text:
            return self._fallback("model returned an empty response")
        return ModelReply(text=text, fallback=False, endpoint=f"{self.endpoint}/api/generate", model=self.model)

    def _fallback(self, reason: str) -> ModelReply:
        return ModelReply(
            text=f"[FALLBACK: local model unavailable — {reason}] Wanted level increased; react after model is online.",
            fallback=True,
            endpoint=f"{self.endpoint}/api/generate",
            model=self.model,
        )


class WantedTracker:
    def __init__(self, model_client: OllamaReactionClient, *, reaction_log: Optional[Callable[[WantedReaction], None]] = None):
        self._model_client = model_client
        self._reaction_log = reaction_log
        self._previous_wanted: Optional[int] = None

    def process_state(self, state: dict[str, Any]) -> Optional[WantedReaction]:
        current = int(state["wanted"])
        previous = self._previous_wanted
        self._previous_wanted = current
        if previous is None or current <= previous:
            return None
        context = build_wanted_context(previous, current, state)
        reply = self._model_client.generate_wanted_reaction(previous_wanted=previous, current_wanted=current, context=context)
        reaction = WantedReaction(previous, current, context, reply.text, reply.fallback, reply.endpoint, reply.model)
        if self._reaction_log:
            self._reaction_log(reaction)
        return reaction


def print_reaction(reaction: WantedReaction) -> None:
    marker = "MODEL FALLBACK" if reaction.fallback else "HERMES REACTION"
    print("=" * 72, flush=True)
    print(f"[{marker}] wanted {reaction.previous_wanted} -> {reaction.current_wanted}", flush=True)
    print(reaction.text, flush=True)
    print(f"model={reaction.model} endpoint={reaction.endpoint}", flush=True)
    print("=" * 72, flush=True)


def serve(*, host: str = HOST, port: int = PORT, logs_dir: Path = DEFAULT_LOGS_DIR, model_client: Optional[OllamaReactionClient] = None) -> None:
    tracker = WantedTracker(model_client or OllamaReactionClient(), reaction_log=lambda r: append_reaction(r, logs_dir=logs_dir))
    print(f"GtaCopilot brain listening on {host}:{port} | model={tracker._model_client.model} endpoint={tracker._model_client.endpoint}/api/generate", flush=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        while True:
            conn, addr = server.accept()
            print(f"brain accepted state stream from {addr[0]}:{addr[1]}", flush=True)
            with conn, conn.makefile("r", encoding="utf-8", newline="\n") as stream:
                for line in stream:
                    raw = line.rstrip("\r\n")
                    if not raw:
                        continue
                    append_raw_line(raw, logs_dir=logs_dir)
                    try:
                        state = parse_state_line(raw)
                    except ValueError as exc:
                        print(f"invalid state line: {exc}: {raw[:200]}", file=sys.stderr, flush=True)
                        continue
                    print(format_summary(state), flush=True)
                    reaction = tracker.process_state(state)
                    if reaction:
                        print_reaction(reaction)
            print("brain state stream disconnected; waiting for reconnect", flush=True)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Listen for GTA Copilot state JSONL and print brain reactions.")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--logs-dir", type=Path, default=DEFAULT_LOGS_DIR)
    parser.add_argument("--ollama-endpoint", default=None)
    parser.add_argument("--ollama-model", default=None)
    args = parser.parse_args(argv)
    client = OllamaReactionClient(endpoint=args.ollama_endpoint, model=args.ollama_model)
    serve(host=args.host, port=args.port, logs_dir=args.logs_dir, model_client=client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
