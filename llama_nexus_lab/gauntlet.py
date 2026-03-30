from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


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


def save_gauntlet_spec(path: str | Path, spec: GauntletSpec) -> None:
    spec.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(spec), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_gauntlet_spec(path: str | Path) -> GauntletSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    spec = GauntletSpec(**payload)
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
