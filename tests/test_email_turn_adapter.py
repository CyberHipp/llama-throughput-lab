import json
import tempfile
import unittest
from pathlib import Path

from llama_nexus_lab.email_turn_adapter import (
    build_turn_packet,
    load_turn_packet,
    serialize_turn_packet,
    validate_turn_packet,
)


class EmailTurnAdapterTests(unittest.TestCase):
    def test_turn_packet_validation_and_roundtrip(self):
        packet = build_turn_packet(
            game_id="g-1",
            turn=1,
            actor="white",
            move="e2e4",
            state={"fen": "startpos"},
            legal_next=["e7e5"],
            ts_utc="2026-03-30T00:00:00Z",
        )
        validate_turn_packet(packet)
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = serialize_turn_packet(packet, Path(tmp_dir) / "turn_packet_v1.json")
            loaded = load_turn_packet(path)
        self.assertEqual(packet, loaded)

    def test_hash_and_idempotency_are_deterministic(self):
        kwargs = {
            "game_id": "g-2",
            "turn": 2,
            "actor": "black",
            "move": "e7e5",
            "state": {"fen": "fen-state"},
            "legal_next": ["g1f3"],
            "ts_utc": "2026-03-30T00:00:01Z",
        }
        packet_a = build_turn_packet(**kwargs)
        packet_b = build_turn_packet(**kwargs)
        self.assertEqual(packet_a["idempotency_key"], packet_b["idempotency_key"])
        self.assertEqual(packet_a["hash"], packet_b["hash"])

    def test_missing_required_field_fails(self):
        packet = {
            "protocol": "email-turn-v1",
            "game_type": "chess",
        }
        with self.assertRaises(ValueError):
            validate_turn_packet(packet)


if __name__ == "__main__":
    unittest.main()
