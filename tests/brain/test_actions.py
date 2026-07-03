"""Unit tests for Phase 5a — action system (intent matcher, ActionClient, ack correlation).

All tests are self-contained and run without a game or Ollama.
"""

import io
import json
import queue
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.brain.actions import (
    GAZETTEER,
    WHITELISTED_ACTIONS,
    ActionAck,
    ActionClient,
    ActionRequest,
    _IDGenerator,
    _extract_place,
    append_action_log,
    is_action_whitelisted,
    match_intent,
)
from src.brain.overlay import LineTag


# -----------------------------------------------------------------------
# Gazetteer sanity
# -----------------------------------------------------------------------

class GazetteerTests(unittest.TestCase):
    def test_gazetteer_has_at_least_15_entries(self):
        self.assertGreaterEqual(len(GAZETTEER), 15)

    def test_all_entries_have_x_y(self):
        for name, coords in GAZETTEER.items():
            self.assertIn("x", coords, f"{name} missing x")
            self.assertIn("y", coords, f"{name} missing y")
            self.assertIsInstance(coords["x"], (int, float), f"{name} x is not numeric")
            self.assertIsInstance(coords["y"], (int, float), f"{name} y is not numeric")


# -----------------------------------------------------------------------
# Intent matcher
# -----------------------------------------------------------------------

class IntentMatcherTests(unittest.TestCase):
    def test_set_waypoint_to_airport(self):
        result = match_intent("set a waypoint to the airport")
        self.assertIsNotNone(result)
        self.assertEqual(result.action, "set_waypoint")
        self.assertEqual(result.place_name, "airport")
        self.assertEqual(result.params["x"], GAZETTEER["airport"]["x"])
        self.assertEqual(result.params["y"], GAZETTEER["airport"]["y"])

    def test_take_me_to_hospital(self):
        result = match_intent("take me to the hospital")
        self.assertIsNotNone(result)
        self.assertEqual(result.action, "set_waypoint")
        self.assertEqual(result.place_name, "hospital")

    def test_mark_on_map(self):
        result = match_intent("mark the airport on the map")
        self.assertIsNotNone(result)
        self.assertEqual(result.place_name, "airport")

    def test_go_to_place(self):
        result = match_intent("go to sandy shores")
        self.assertIsNotNone(result)
        self.assertEqual(result.place_name, "sandy shores")

    def test_navigate_to_vinewood(self):
        result = match_intent("navigate to vinewood sign")
        self.assertIsNotNone(result)
        self.assertEqual(result.place_name, "vinewood sign")

    def test_drive_to_casino(self):
        result = match_intent("drive to the casino")
        self.assertIsNotNone(result)
        self.assertEqual(result.place_name, "casino")

    def test_case_insensitive(self):
        result = match_intent("SET A WAYPOINT TO THE AIRPORT")
        self.assertIsNotNone(result)
        self.assertEqual(result.place_name, "airport")

    def test_no_match_random_speech(self):
        result = match_intent("what's the weather like today")
        self.assertIsNone(result)

    def test_no_match_empty(self):
        result = match_intent("")
        self.assertIsNone(result)

    def test_no_match_unknown_place(self):
        result = match_intent("set a waypoint to atlantis")
        self.assertIsNone(result)

    def test_partial_place_name(self):
        """'maze bank' should match even in a longer phrase."""
        result = match_intent("waypoint to maze bank tower please")
        self.assertIsNotNone(result)
        # Should match the longer name first (greedy)
        self.assertEqual(result.place_name, "maze bank tower")

    def test_head_to_pattern(self):
        result = match_intent("head to fort zancudo")
        self.assertIsNotNone(result)
        self.assertEqual(result.place_name, "fort zancudo")

    def test_action_ids_are_unique(self):
        r1 = match_intent("set a waypoint to the airport")
        r2 = match_intent("take me to hospital")
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        self.assertNotEqual(r1.id, r2.id)


# -----------------------------------------------------------------------
# Whitelist mirror
# -----------------------------------------------------------------------

class WhitelistTests(unittest.TestCase):
    def test_set_waypoint_is_whitelisted(self):
        self.assertTrue(is_action_whitelisted("set_waypoint"))

    def test_spawn_companion_is_whitelisted(self):
        self.assertTrue(is_action_whitelisted("spawn_companion"))

    def test_heal_player_is_whitelisted(self):
        self.assertTrue(is_action_whitelisted("heal_player"))

    def test_unknown_action_not_whitelisted(self):
        self.assertFalse(is_action_whitelisted("give_money"))
        self.assertFalse(is_action_whitelisted("set_weather"))


# -----------------------------------------------------------------------
# ActionRequest wire format
# -----------------------------------------------------------------------

class WireFormatTests(unittest.TestCase):
    def test_to_wire_json(self):
        req = ActionRequest(
            id=42,
            action="set_waypoint",
            params={"x": -1034.0, "y": -2733.0},
            place_name="airport",
        )
        wire = req.to_wire()
        parsed = json.loads(wire)
        self.assertEqual(parsed["type"], "action")
        self.assertEqual(parsed["id"], 42)
        self.assertEqual(parsed["action"], "set_waypoint")
        self.assertAlmostEqual(parsed["params"]["x"], -1034.0)
        self.assertAlmostEqual(parsed["params"]["y"], -2733.0)


# -----------------------------------------------------------------------
# ActionClient — ack correlation with a real localhost socket
# -----------------------------------------------------------------------

class ActionClientAckTests(unittest.TestCase):
    """Test send_action() + feed_ack() correlation over a real localhost socket."""

    def test_send_and_receive_ack(self):
        """Full round trip: client sends action, fake mod server acks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            overlay_msgs = []
            client = ActionClient(
                timeout_s=2.0,
                logs_dir=logs_dir,
                on_overlay=lambda text: overlay_msgs.append(text),
            )

            # Set up a real TCP server to act as the mod
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(("127.0.0.1", 0))
            port = server_sock.getsockname()[1]
            server_sock.listen(1)

            # Connect as the "brain"
            brain_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            brain_sock.connect(("127.0.0.1", port))
            mod_conn, _ = server_sock.accept()

            # Register the write side for the client
            write_file = brain_sock.makefile("w", encoding="utf-8", newline="\n")
            client.set_connection(write_file)

            # Background: mod reads the request, sends back an ack
            request = ActionRequest(
                id=99, action="set_waypoint",
                params={"x": -1034.0, "y": -2733.0}, place_name="airport",
            )

            def mock_mod():
                """Read request from brain, send ack back."""
                stream = mod_conn.makefile("r", encoding="utf-8", newline="\n")
                line = stream.readline()
                parsed = json.loads(line)
                # Send ack back through the mod_conn
                ack_line = json.dumps({"ack": parsed["id"], "ok": True}) + "\n"
                mod_conn.sendall(ack_line.encode("utf-8"))

            mod_thread = threading.Thread(target=mock_mod)
            mod_thread.start()

            # Feed ack in a background thread (simulating what listener does)
            def ack_feeder():
                """Read ack from the brain socket's read stream."""
                read_stream = brain_sock.makefile("r", encoding="utf-8", newline="\n")
                ack_raw = read_stream.readline().strip()
                if ack_raw:
                    client.feed_ack(ack_raw)

            ack_thread = threading.Thread(target=ack_feeder)
            ack_thread.start()

            ack = client.send_action(request)
            mod_thread.join(timeout=2)
            ack_thread.join(timeout=2)

            # Verify ack
            self.assertIsNotNone(ack)
            self.assertTrue(ack.ok)
            self.assertEqual(ack.id, 99)

            # Verify log was written
            log_files = list(logs_dir.glob("actions-*.jsonl"))
            self.assertEqual(len(log_files), 1)
            with log_files[0].open() as f:
                entries = [json.loads(line) for line in f]
            self.assertGreaterEqual(len(entries), 1)
            self.assertEqual(entries[-1]["request_id"], 99)
            self.assertTrue(entries[-1]["ack_ok"])

            # Cleanup
            client.clear_connection()
            for s in (brain_sock, mod_conn, server_sock):
                try:
                    s.close()
                except Exception:
                    pass

    def test_timeout_on_no_ack(self):
        """If mod never sends an ack, send_action returns None after timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            client = ActionClient(timeout_s=0.3, logs_dir=logs_dir)

            # Use a StringIO-like pipe to simulate a connection that never responds
            write_buf = io.StringIO()
            client.set_connection(write_buf)

            request = ActionRequest(
                id=100, action="set_waypoint",
                params={"x": 0, "y": 0}, place_name="test",
            )
            ack = client.send_action(request)
            self.assertIsNone(ack)

            # Verify timeout log
            log_files = list(logs_dir.glob("actions-*.jsonl"))
            self.assertEqual(len(log_files), 1)
            with log_files[0].open() as f:
                entry = json.loads(f.readline())
            self.assertEqual(entry["ack_err"], "timeout")

    def test_disconnected_send_fails_gracefully(self):
        """If no connection, send_action logs disconnected and returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            client = ActionClient(timeout_s=0.3, logs_dir=logs_dir)
            # No set_connection() call — client is disconnected

            request = ActionRequest(
                id=101, action="set_waypoint",
                params={"x": 0, "y": 0}, place_name="test",
            )
            ack = client.send_action(request)
            self.assertIsNone(ack)

    def test_refuses_non_whitelisted_action(self):
        """Non-whitelisted actions are refused without sending."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            client = ActionClient(timeout_s=0.3, logs_dir=logs_dir)

            request = ActionRequest(
                id=102, action="set_weather",
                params={}, place_name="sunny",
            )
            ack = client.send_action(request)
            self.assertIsNone(ack)

            # Verify refused log
            log_files = list(logs_dir.glob("actions-*.jsonl"))
            self.assertEqual(len(log_files), 1)
            with log_files[0].open() as f:
                entry = json.loads(f.readline())
            self.assertTrue(entry["refused"])


# -----------------------------------------------------------------------
# ActionClient — feed_ack parsing
# -----------------------------------------------------------------------

class FeedAckTests(unittest.TestCase):
    def test_valid_ack_parsed(self):
        client = ActionClient(logs_dir=Path(tempfile.mkdtemp()))
        ack = client.feed_ack('{"ack": 5, "ok": true, "err": null}')
        self.assertIsNotNone(ack)
        self.assertEqual(ack.id, 5)
        self.assertTrue(ack.ok)
        self.assertIsNone(ack.err)

    def test_nack_parsed(self):
        client = ActionClient(logs_dir=Path(tempfile.mkdtemp()))
        ack = client.feed_ack('{"ack": 6, "ok": false, "err": "unknown action"}')
        self.assertIsNotNone(ack)
        self.assertFalse(ack.ok)
        self.assertEqual(ack.err, "unknown action")

    def test_non_ack_line_returns_none(self):
        client = ActionClient(logs_dir=Path(tempfile.mkdtemp()))
        result = client.feed_ack('{"t":123,"health":200}')
        self.assertIsNone(result)

    def test_invalid_json_returns_none(self):
        client = ActionClient(logs_dir=Path(tempfile.mkdtemp()))
        result = client.feed_ack("not json at all")
        self.assertIsNone(result)


# -----------------------------------------------------------------------
# Action log file
# -----------------------------------------------------------------------

class ActionLogTests(unittest.TestCase):
    def test_append_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir)
            entry = {"request_id": 1, "action": "set_waypoint"}
            path = append_action_log(entry, logs_dir=logs_dir, date_text="20260703")
            self.assertTrue(path.exists())
            self.assertEqual(path.name, "actions-20260703.jsonl")
            with path.open() as f:
                data = json.loads(f.readline())
            self.assertEqual(data["request_id"], 1)


# -----------------------------------------------------------------------
# ID generator
# -----------------------------------------------------------------------

class IDGeneratorTests(unittest.TestCase):
    def test_monotonically_increasing(self):
        gen = _IDGenerator()
        ids = [gen.next() for _ in range(100)]
        self.assertEqual(ids, list(range(1, 101)))

    def test_thread_safe(self):
        gen = _IDGenerator()
        results = []
        lock = threading.Lock()

        def worker():
            for _ in range(50):
                val = gen.next()
                with lock:
                    results.append(val)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 200)
        self.assertEqual(len(set(results)), 200)  # all unique


# -----------------------------------------------------------------------
# Overlay ACTION tag
# -----------------------------------------------------------------------

class OverlayActionTagTests(unittest.TestCase):
    def test_action_tag_exists(self):
        self.assertEqual(LineTag.ACTION.value, "action")

    def test_action_colour_defined(self):
        from src.brain.overlay import TAG_COLOURS
        self.assertIn(LineTag.ACTION, TAG_COLOURS)
        # Should be orange-ish
        self.assertEqual(TAG_COLOURS[LineTag.ACTION], "#f4845f")


# -----------------------------------------------------------------------
# Phase 5b: companion intent + per-action phrases
# -----------------------------------------------------------------------

class CompanionIntentTests(unittest.TestCase):
    def test_spawn_companion_phrases_match(self):
        from src.brain.actions import match_intent

        for phrase in [
            "spawn a companion",
            "Spawn companion.",
            "call backup",
            "I need backup right now!",
            "send backup please",
            "give me a companion",
            "get me another bodyguard",
            "bring me a buddy",
        ]:
            intent = match_intent(phrase)
            self.assertIsNotNone(intent, phrase)
            self.assertEqual(intent.action, "spawn_companion", phrase)
            self.assertEqual(intent.params, {}, phrase)

    def test_companion_does_not_hijack_waypoints(self):
        from src.brain.actions import match_intent

        intent = match_intent("take me to the airport")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.action, "set_waypoint")

    def test_unrelated_speech_matches_nothing(self):
        from src.brain.actions import match_intent

        for phrase in ["back up the car", "what's my backup plan", "hello there"]:
            self.assertIsNone(match_intent(phrase), phrase)

    def test_companion_wire_format_has_empty_params(self):
        from src.brain.actions import match_intent
        import json as _json

        wire = _json.loads(match_intent("call backup").to_wire())
        self.assertEqual(wire["action"], "spawn_companion")
        self.assertEqual(wire["params"], {})
        self.assertEqual(wire["type"], "action")


class ExpressionActionTests(unittest.TestCase):
    def test_make_talking_request_wire(self):
        from src.brain.actions import make_talking_request

        wire = json.loads(make_talking_request(4217.9).to_wire())
        self.assertEqual(wire["action"], "companion_talking")
        self.assertEqual(wire["params"], {"duration_ms": 4217})

    def test_make_gesture_request_wire(self):
        from src.brain.actions import make_gesture_request

        wire = json.loads(make_gesture_request("wave").to_wire())
        self.assertEqual(wire["action"], "companion_gesture")
        self.assertEqual(wire["params"], {"name": "wave"})

    def test_expression_actions_whitelisted(self):
        self.assertTrue(is_action_whitelisted("companion_talking"))
        self.assertTrue(is_action_whitelisted("companion_gesture"))
        self.assertTrue(is_action_whitelisted("companion_stay"))
        self.assertTrue(is_action_whitelisted("companion_follow"))

    def test_send_action_no_wait_logs_and_returns_immediately(self):
        import tempfile
        from src.brain.actions import make_talking_request

        with tempfile.TemporaryDirectory() as tmp:
            logs_dir = Path(tmp)
            client = ActionClient(timeout_s=5.0, logs_dir=logs_dir)

            class FakeConn:
                def __init__(self):
                    self.lines = []
                def write(self, s):
                    self.lines.append(s)
                def flush(self):
                    pass

            conn = FakeConn()
            client.set_connection(conn)

            start = time.monotonic()
            result = client.send_action(make_talking_request(1500), wait=False)
            elapsed = time.monotonic() - start

            self.assertIsNone(result)
            self.assertLess(elapsed, 1.0)  # must not block for the 5s timeout
            self.assertEqual(len(conn.lines), 1)
            log_files = list(logs_dir.glob("actions-*.jsonl"))
            self.assertEqual(len(log_files), 1)
            entry = json.loads(log_files[0].read_text(encoding="utf-8").strip())
            self.assertEqual(entry["action"], "companion_talking")
            self.assertEqual(entry["ack_err"], "not awaited")

    def test_speaker_on_audio_ready_reports_duration(self):
        import numpy as np
        from src.brain.voice.speaker import Speaker

        class FakeTTS:
            def synthesize(self, text):
                return np.zeros(11025, dtype=np.int16), 22050  # 500 ms

        class FakePlayback:
            def play(self, audio_int16, *, samplerate):
                pass

        durations = []
        spk = Speaker(tts_backend=FakeTTS(), playback_backend=FakePlayback())
        spk.speak("hello there", on_audio_ready=durations.append)

        self.assertEqual(len(durations), 1)
        self.assertAlmostEqual(durations[0], 500.0, delta=1.0)


class ActionPhraseTests(unittest.TestCase):
    def test_confirmation_per_action(self):
        from src.brain.actions import ActionRequest, confirmation_phrase

        wp = ActionRequest(id=1, action="set_waypoint", params={"x": 1.0, "y": 2.0}, place_name="airport")
        self.assertEqual(confirmation_phrase(wp), "Waypoint set — airport.")

        comp = ActionRequest(id=2, action="spawn_companion", params={}, place_name="backup")
        self.assertIn("six", confirmation_phrase(comp))
        self.assertNotIn("Waypoint", confirmation_phrase(comp))

    def test_failure_phrase_handles_already_active(self):
        from src.brain.actions import ActionRequest, failure_phrase

        comp = ActionRequest(id=3, action="spawn_companion", params={}, place_name="backup")
        self.assertIn("already got", failure_phrase(comp, "companion already active"))
        self.assertIn("Couldn't do it", failure_phrase(comp, "queue full"))


class HealIntentTests(unittest.TestCase):
    def test_heal_player_phrases_match(self):
        from src.brain.actions import match_intent
        
        for phrase in [
            "heal me",
            "patch me up",
            "fix me up please",
            "i need health",
        ]:
            intent = match_intent(phrase)
            self.assertIsNotNone(intent, phrase)
            self.assertEqual(intent.action, "heal_player", phrase)
            self.assertEqual(intent.params, {}, phrase)
            
    def test_heal_does_not_hijack_others(self):
        from src.brain.actions import match_intent
        
        # Test it doesn't match false positives
        self.assertIsNone(match_intent("healthy food"))
        self.assertIsNone(match_intent("fix the car"))

    def test_heal_confirmation_phrase(self):
        from src.brain.actions import ActionRequest, confirmation_phrase
        
        heal = ActionRequest(id=4, action="heal_player", params={}, place_name="health")
        self.assertEqual(confirmation_phrase(heal), "Patched up — you're good.")


class Phase6IntentTests(unittest.TestCase):
    def test_stay_intent_match(self):
        from src.brain.actions import match_intent
        
        phrases = ["wait here", "stay here", "hold position", "stay put"]
        for phrase in phrases:
            intent = match_intent(phrase)
            self.assertIsNotNone(intent, phrase)
            self.assertEqual(intent.action, "companion_stay", phrase)

    def test_follow_intent_match(self):
        from src.brain.actions import match_intent
        
        phrases = ["follow me", "stick with me", "come with me", "keep up"]
        for phrase in phrases:
            intent = match_intent(phrase)
            self.assertIsNotNone(intent, phrase)
            self.assertEqual(intent.action, "companion_follow", phrase)

    def test_panicked_speech_is_not_a_follow_command(self):
        from src.brain.actions import match_intent

        # Reviewer fix: bare "on me" was a follow trigger — "the cops are on
        # me!" must never command the companion.
        self.assertIsNone(match_intent("the cops are on me!"))
        self.assertIsNone(match_intent("they're on me, help!"))

    def test_no_bare_lets_go(self):
        from src.brain.actions import match_intent
        
        # We must not match a bare "let's go"
        intent = match_intent("let's go")
        self.assertIsNone(intent, "let's go matched something inappropriately")
        intent2 = match_intent("lets go")
        self.assertIsNone(intent2, "lets go matched something inappropriately")

    def test_gesture_intent_match(self):
        from src.brain.actions import match_intent
        
        # wave
        phrases_wave = ["wave", "say hi", "wave at me"]
        for phrase in phrases_wave:
            intent = match_intent(phrase)
            self.assertIsNotNone(intent, phrase)
            self.assertEqual(intent.action, "companion_gesture", phrase)
            self.assertEqual(intent.params.get("name"), "wave", phrase)

        # nod
        intent_nod = match_intent("nod")
        self.assertIsNotNone(intent_nod)
        self.assertEqual(intent_nod.action, "companion_gesture")
        self.assertEqual(intent_nod.params.get("name"), "nod")

    def test_false_positive_waive(self):
        from src.brain.actions import match_intent
        intent = match_intent("waive the fee")
        self.assertIsNone(intent, "matched waive instead of wave")

    def test_phase6_phrases(self):
        from src.brain.actions import ActionRequest, confirmation_phrase, failure_phrase
        
        req_stay = ActionRequest(id=10, action="companion_stay", params={}, place_name="stay")
        self.assertEqual(confirmation_phrase(req_stay), "Holding position.")
        self.assertIn("call backup first", failure_phrase(req_stay, "no companion active"))
        self.assertIn("didn't make it", failure_phrase(req_stay, "companion is dead"))
        
        req_follow = ActionRequest(id=11, action="companion_follow", params={}, place_name="follow")
        self.assertEqual(confirmation_phrase(req_follow), "Right behind you.")
        
        req_wave = ActionRequest(id=12, action="companion_gesture", params={"name": "wave"}, place_name="wave")
        self.assertEqual(confirmation_phrase(req_wave), "Hello there.")


if __name__ == "__main__":
    unittest.main()
