from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PromptAssetManifest:
    asset_id: str
    version: str
    owner: str
    kind: str
    purpose: str
    output_fields: tuple[str, ...]
    source_path: str


@dataclass(frozen=True)
class AgentContract:
    agent_id: str
    purpose: str
    model: str
    outputs: tuple[str, ...]
    receipt_required: bool


ROOT = Path(__file__).resolve().parents[1]


def _read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_prompt_asset_manifests(path: str | None = None) -> tuple[PromptAssetManifest, ...]:
    manifest_path = Path(path) if path else ROOT / "prompt_library" / "prompt_assets.yaml"
    data = _read_yaml(manifest_path)
    rows = data.get("assets", [])
    return tuple(
        PromptAssetManifest(
            asset_id=row["asset_id"],
            version=row["version"],
            owner=row["owner"],
            kind=row["kind"],
            purpose=row["purpose"],
            output_fields=tuple(row.get("output_fields", [])),
            source_path=row["source_path"],
        )
        for row in rows
    )


def load_agent_contracts(path: str | None = None) -> tuple[AgentContract, ...]:
    contracts_path = Path(path) if path else ROOT / "agent_roles" / "agent_contracts.yaml"
    data = _read_yaml(contracts_path)
    rows = data.get("agents", [])
    return tuple(
        AgentContract(
            agent_id=row["agent_id"],
            purpose=row["purpose"],
            model=row["model"],
            outputs=tuple(row.get("outputs", [])),
            receipt_required=bool(row.get("receipt_required", True)),
        )
        for row in rows
    )


def manifest_by_asset_id(asset_id: str, manifests: tuple[PromptAssetManifest, ...]) -> PromptAssetManifest:
    for manifest in manifests:
        if manifest.asset_id == asset_id:
            return manifest
    raise KeyError(f"Unknown prompt asset: {asset_id}")


def contract_by_agent_id(agent_id: str, contracts: tuple[AgentContract, ...]) -> AgentContract:
    for contract in contracts:
        if contract.agent_id == agent_id:
            return contract
    raise KeyError(f"Unknown agent contract: {agent_id}")
