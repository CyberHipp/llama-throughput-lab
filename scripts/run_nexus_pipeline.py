#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from llama_nexus_lab import load_nexus_config, run_research_pipeline, write_pipeline_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run llama-nexus-lab researcher pipeline")
    parser.add_argument("--query", required=True, help="User query to research")
    parser.add_argument(
        "--config",
        default="configs/nexus/default.json",
        help="Path to nexus config file (JSON recommended)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_nexus_config(args.config)
    result = run_research_pipeline(args.query, config)
    artifacts = write_pipeline_artifacts(result, config.runtime.artifacts_dir)
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "confidence": result.confidence,
                "artifacts": artifacts,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
