from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class GauntletSpec:
    gauntlet_name: str
    query: str
    max_search_intents: int
    strict_citation_required: bool
    dry_run: bool
    require_verify_pass: bool

    def validate(self) -> None:
        if not self.gauntlet_name.strip():
            raise ValueError("gauntlet_name must be non-empty")
        if not self.query.strip():
            raise ValueError("query must be non-empty")
        if self.max_search_intents <= 0:
            raise ValueError("max_search_intents must be > 0")


@dataclass(frozen=True)
class QueueItem:
    gauntlet_name: str
    config_path: str
    command: tuple[str, ...]


def save_gauntlet_spec(path: str | Path, spec: GauntletSpec) -> None:
    spec.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(spec), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_gauntlet_spec(path: str | Path) -> GauntletSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "query" not in payload and "query_template" in payload:
        payload = dict(payload)
        payload["query"] = payload["query_template"]
    allowed = {
        "gauntlet_name",
        "query",
        "max_search_intents",
        "strict_citation_required",
        "dry_run",
        "require_verify_pass",
    }
    materialized = {key: payload[key] for key in allowed if key in payload}
    spec = GauntletSpec(**materialized)
    spec.validate()
    return spec


def build_temp_runtime_config(base_config_path: str | Path, spec: GauntletSpec, out_path: str | Path) -> str:
    spec.validate()
    base_path = Path(base_config_path)
    if not base_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_path}")

    config = json.loads(base_path.read_text(encoding="utf-8"))
    pipeline = dict(config.get("pipeline") or {})
    pipeline["max_search_intents"] = spec.max_search_intents
    pipeline["strict_citation_required"] = spec.strict_citation_required
    pipeline["dry_run"] = spec.dry_run
    config["pipeline"] = pipeline

    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(destination)


def write_queue_manifest(path: str | Path, *, queue_id: str, stop_on_fail: bool, items: list[QueueItem]) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "queue_id": queue_id,
        "stop_on_fail": stop_on_fail,
        "items": [
            {"gauntlet_name": item.gauntlet_name, "config_path": item.config_path, "command": list(item.command)}
            for item in items
        ],
    }
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)


def process_queue(
    *,
    queue_items: list[QueueItem],
    stop_on_fail: bool,
    run_item: Callable[[QueueItem], dict],
    receipt_path: str | Path,
    queue_id: str | None = None,
) -> str:
    queue_label = queue_id or f"queue-{uuid.uuid4().hex[:10]}"
    receipts: list[dict] = []
    queue_failed = False

    for item in queue_items:
        if queue_failed and stop_on_fail:
            receipts.append(
                {
                    "gauntlet_name": item.gauntlet_name,
                    "config_path": item.config_path,
                    "run_id": None,
                    "status": "skipped",
                    "reason": "skipped due to prior failure and stop_on_fail",
                    "artifacts": None,
                }
            )
            continue

        result = run_item(item)
        exit_code = int(result.get("exit_code", 1))
        status = "pass" if exit_code == 0 else "fail"
        reason = "none" if status == "pass" else result.get("reason", f"exit_code={exit_code}")
        receipts.append(
            {
                "gauntlet_name": item.gauntlet_name,
                "config_path": item.config_path,
                "run_id": result.get("run_id"),
                "status": status,
                "reason": reason,
                "artifacts": result.get("artifacts"),
            }
        )
        if status == "fail":
            queue_failed = True

    payload = {
        "queue_id": queue_label,
        "stop_on_fail": stop_on_fail,
        "result": "fail" if queue_failed else "pass",
        "items": receipts,
    }
    target = Path(receipt_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(target)
