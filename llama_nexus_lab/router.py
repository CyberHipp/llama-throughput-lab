from __future__ import annotations

from llama_nexus_lab.models import ModelProfile, NexusConfig


def select_model(task: str, config: NexusConfig) -> ModelProfile:
    profile_map = {profile.name: profile for profile in config.model_profiles}
    for rule in config.router_rules:
        if rule.task != task:
            continue
        if rule.preferred_model in profile_map:
            return profile_map[rule.preferred_model]
        for fallback in rule.fallback_models:
            if fallback in profile_map:
                return profile_map[fallback]
        break
    raise ValueError(f"No model profile available for task '{task}'")


def expand_intents(query: str, max_intents: int) -> list[str]:
    tokens = [token.strip(".,:;!? ") for token in query.split(" ") if token.strip()]
    intents = [query]
    if len(tokens) > 4:
        intents.append(" ".join(tokens[:4]))
    if len(tokens) > 7:
        intents.append(" ".join(tokens[-4:]))
    intents.extend(
        [
            f"{query} benchmarks",
            f"{query} architecture",
            f"{query} failure modes",
        ]
    )
    unique: list[str] = []
    for intent in intents:
        if intent not in unique:
            unique.append(intent)
    return unique[:max_intents]
