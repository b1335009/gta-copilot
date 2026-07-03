import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.brain import state_listener


SAMPLE_ON_FOOT = {
    "t": 1783039181392,
    "health": 150,
    "max_health": 200,
    "armor": 0,
    "wanted": 1,
    "pos": {"x": -152.4, "y": -1517.7, "z": 34.0},
    "vehicle": None,
}

SAMPLE_VEHICLE = {
    "t": 1783038827899,
    "health": 200,
    "max_health": 200,
    "armor": 0,
    "wanted": 0,
    "pos": {"x": -22.9, "y": -1435.2, "z": 30.1},
    "vehicle": {"name": "Bagger", "speed_kmh": 10},
}


class FakeReactionClient:
    endpoint = "fake://model"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def generate_wanted_reaction(self, *, previous_wanted, current_wanted, context):
        self.calls.append((previous_wanted, current_wanted, context))
        return state_listener.ModelReply(
            text=f"Wanted jump {previous_wanted}->{current_wanted}: keep moving.",
            fallback=False,
            endpoint=self.endpoint,
            model=self.model,
        )


class StateListenerUnitTests(unittest.TestCase):
    def test_parse_state_line_requires_exact_phase1_schema(self):
        line = json.dumps(SAMPLE_VEHICLE)

        parsed = state_listener.parse_state_line(line)

        self.assertEqual(parsed, SAMPLE_VEHICLE)
        with self.assertRaisesRegex(ValueError, "missing required keys"):
            bad = dict(SAMPLE_VEHICLE)
            bad.pop("vehicle")
            state_listener.parse_state_line(json.dumps(bad))

    def test_format_summary_is_compact_and_includes_key_state(self):
        summary = state_listener.format_summary(SAMPLE_VEHICLE)

        self.assertIn("wanted=0", summary)
        self.assertIn("hp=200/200", summary)
        self.assertIn("vehicle=Bagger@10km/h", summary)
        self.assertIn("pos=(-22.9,-1435.2,30.1)", summary)

    def test_wanted_tracker_calls_model_only_on_increase_and_logs_reaction(self):
        client = FakeReactionClient()
        logged = []
        tracker = state_listener.WantedTracker(client, reaction_log=logged.append)

        self.assertIsNone(tracker.process_state({**SAMPLE_ON_FOOT, "wanted": 0}))
        self.assertIsNone(tracker.process_state({**SAMPLE_ON_FOOT, "wanted": 0, "health": 149}))
        reaction = tracker.process_state({**SAMPLE_ON_FOOT, "wanted": 2})

        self.assertIsNotNone(reaction)
        self.assertEqual(len(client.calls), 1)
        previous, current, context = client.calls[0]
        self.assertEqual((previous, current), (0, 2))
        self.assertIn("wanted 0 -> 2", context)
        self.assertIn("health 150/200", context)
        self.assertIn("on foot", context)
        self.assertIn("pos -152.4,-1517.7,34.0", context)
        self.assertEqual(reaction.text, "Wanted jump 0->2: keep moving.")
        self.assertFalse(reaction.fallback)
        self.assertEqual(logged, [reaction])

    def test_clean_model_text_keeps_first_sentence_only(self):
        cleaned = state_listener.clean_model_text(
            '"Haste needed, head to the alley now! Heal and arm up before cops close in."'
        )

        self.assertEqual(cleaned, "Haste needed, head to the alley now!")

    def test_companion_field_is_optional_and_validated(self):
        # Milestone 6: mod DLLs >= 6a emit "companion"; older lines omit it.
        with_companion = {**SAMPLE_ON_FOOT, "companion": {"health": 175, "dead": False}}
        parsed = state_listener.parse_state_line(json.dumps(with_companion))
        self.assertEqual(parsed["companion"], {"health": 175, "dead": False})
        self.assertIn("companion_hp=175", state_listener.format_summary(parsed))

        null_companion = {**SAMPLE_ON_FOOT, "companion": None}
        parsed = state_listener.parse_state_line(json.dumps(null_companion))
        self.assertNotIn("companion", state_listener.format_summary(parsed))

        dead = {**SAMPLE_ON_FOOT, "companion": {"health": 0, "dead": True}}
        self.assertIn("companion=DEAD", state_listener.format_summary(
            state_listener.parse_state_line(json.dumps(dead))))

        with self.assertRaisesRegex(ValueError, "companion"):
            bad = {**SAMPLE_ON_FOOT, "companion": {"health": 175}}
            state_listener.parse_state_line(json.dumps(bad))

        with self.assertRaisesRegex(ValueError, "unexpected keys"):
            state_listener.parse_state_line(json.dumps({**SAMPLE_ON_FOOT, "mystery": 1}))

    def test_append_raw_line_logs_to_dated_jsonl_file(self):
        with TemporaryDirectory() as tmp:
            log_path = state_listener.append_raw_line(
                json.dumps(SAMPLE_ON_FOOT),
                logs_dir=Path(tmp),
                date_text="20260702",
            )

            self.assertEqual(log_path.name, "state-20260702.jsonl")
            self.assertEqual(log_path.read_text(encoding="utf-8"), json.dumps(SAMPLE_ON_FOOT) + "\n")


if __name__ == "__main__":
    unittest.main()
