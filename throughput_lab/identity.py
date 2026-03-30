from __future__ import annotations

TOOL_NAME = "llama-throughput-lab"
PRODUCT_NAME = "Llama Throughput Lab"
INTEGRATION_NAME = "llama-nexus-lab"
CONTRACT_VERSION = "nexus-contract-v1"


def identity_contract_info() -> dict[str, str]:
    return {
        "tool_name": TOOL_NAME,
        "product_name": PRODUCT_NAME,
        "integration_name": INTEGRATION_NAME,
        "contract_version": CONTRACT_VERSION,
    }
