from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "protocol",
    "game_type",
    "game_id",
    "turn",
    "actor",
    "move",
    "state",
    "legal_next",
    "ts_utc",
    "idempotency_key",
    "hash",
}


def _stable_payload_for_hash(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": packet["protocol"],
        "game_type": packet["game_type"],
        "game_id": packet["game_id"],
        "turn": packet["turn"],
        "actor": packet["actor"],
        "move": packet["move"],
        "state": packet["state"],
        "legal_next": packet["legal_next"],
        "ts_utc": packet["ts_utc"],
    }


def _compute_hash(packet: dict[str, Any]) -> str:
    body = json.dumps(_stable_payload_for_hash(packet), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _compute_idempotency_key(packet: dict[str, Any]) -> str:
    seed = f"{packet['protocol']}|{packet['game_id']}|{packet['turn']}|{packet['actor']}|{packet['move']}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def build_turn_packet(
    *,
    game_id: str,
    turn: int,
    actor: str,
    move: str,
    state: dict[str, Any],
    legal_next: list[str],
    game_type: str = "chess",
    protocol: str = "email-turn-v1",
    ts_utc: str | None = None,
) -> dict[str, Any]:
    if turn <= 0:
        raise ValueError("turn must be > 0")
    timestamp = ts_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    packet = {
        "protocol": protocol,
        "game_type": game_type,
        "game_id": game_id,
        "turn": turn,
        "actor": actor,
        "move": move,
        "state": state,
        "legal_next": legal_next,
        "ts_utc": timestamp,
    }
    packet["idempotency_key"] = _compute_idempotency_key(packet)
    packet["hash"] = _compute_hash(packet)
    return packet


def validate_turn_packet(packet: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_FIELDS - set(packet.keys()))
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")
    if packet["protocol"] != "email-turn-v1":
        raise ValueError("Unsupported protocol")
    if int(packet["turn"]) <= 0:
        raise ValueError("turn must be > 0")
    if not isinstance(packet["state"], dict):
        raise ValueError("state must be object")
    if not isinstance(packet["legal_next"], list):
        raise ValueError("legal_next must be list")

    expected_idempotency = _compute_idempotency_key(packet)
    expected_hash = _compute_hash(packet)
    if packet["idempotency_key"] != expected_idempotency:
        raise ValueError("idempotency_key mismatch")
    if packet["hash"] != expected_hash:
        raise ValueError("hash mismatch")


def serialize_turn_packet(packet: dict[str, Any], path: str | Path) -> str:
    validate_turn_packet(packet)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)


def load_turn_packet(path: str | Path) -> dict[str, Any]:
    packet = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_turn_packet(packet)
    return packet


def build_email_bundle(packet: dict[str, Any], attachment_path: str) -> dict[str, str]:
    validate_turn_packet(packet)
    fen = packet.get("state", {}).get("fen", "n/a")
    subject = f"[{packet['protocol']}] {packet['game_type']} {packet['game_id']} turn {packet['turn']}"
    plain = (
        f"Protocol: {packet['protocol']}\n"
        f"Game: {packet['game_type']} / {packet['game_id']}\n"
        f"Turn: {packet['turn']}\n"
        f"Actor: {packet['actor']}\n"
        f"Move: {packet['move']}\n"
        f"FEN: {fen}\n"
        f"Idempotency: {packet['idempotency_key']}\n"
    )
    html = (
        f"<h3>{subject}</h3>"
        f"<p><b>Actor:</b> {packet['actor']}<br/>"
        f"<b>Move:</b> {packet['move']}<br/>"
        f"<b>FEN:</b> {fen}<br/>"
        f"<b>Idempotency:</b> {packet['idempotency_key']}</p>"
    )
    return {
        "subject": subject,
        "plain_text": plain,
        "html_text": html,
        "attachment_path": attachment_path,
    }
