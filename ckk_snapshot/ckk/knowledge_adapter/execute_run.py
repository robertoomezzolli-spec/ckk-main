"""Fixed experiment entrypoint executed under OS resource limits.

This file is adapter machinery only. It imports and calls the pinned CKK
repository's real ``grammar.py`` and ``expand.py``; it does not reimplement the
grammar or expansion algorithm.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys
import time
from typing import Any


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _seed(grammar: Any, selector: str) -> list[Any]:
    if selector in {"all", "SEEDS"}:
        return list(grammar.SEEDS)
    if selector == "SEED_R":
        return [grammar.SEED_R]
    if selector.isdigit():
        index = int(selector)
        if 0 <= index < len(grammar.SEEDS):
            return [grammar.SEEDS[index]]
    matches = [item for item in grammar.SEEDS if str(getattr(item, "label", "")) == selector]
    if matches:
        return matches
    raise ValueError("seed selector does not identify a canonical CKK seed")


def execute(request: dict[str, Any], source_directory: Path) -> dict[str, Any]:
    sys.path.insert(0, str(source_directory))
    grammar = importlib.import_module("grammar")
    expand = importlib.import_module("expand")
    selected_seeds = _seed(grammar, request["seed"])
    selected_names = set(request["operators"])
    registered = [op.__name__ for op in [*grammar.UNARY, *grammar.BINARY]]
    unknown = sorted(selected_names.difference(registered))
    if unknown:
        raise ValueError("operators are not registered by pinned grammar: " + ",".join(unknown))
    expand.SEEDS = selected_seeds
    expand.UNARY = [op for op in grammar.UNARY if not selected_names or op.__name__ in selected_names]
    expand.BINARY = [op for op in grammar.BINARY if not selected_names or op.__name__ in selected_names]
    controls = request["controls"]
    expansion = (
        expand.expand_structural_auditable
        if controls == ["structural_identity"]
        else expand.expand_auditable
    )
    limits = request["compute_limits"]
    started = time.monotonic()
    pool, derivations = expansion(levels=limits["levels"], cap=limits["state_cap"])
    if len(derivations) > limits["derivation_cap"]:
        raise RuntimeError("COMPUTATIONAL_LIMIT: derivation_cap exceeded")
    states = list(pool.values())
    provenance = [
        {
            "operator": item.operator,
            "inputs": _jsonable(item.inputs),
            "output": _jsonable(item.output),
            "level": item.level,
        }
        for item in derivations
    ]
    observed_operators = sorted({item.operator for item in derivations})
    state_digest = hashlib.sha256(
        json.dumps(sorted([_jsonable(key) for key in pool], key=lambda item: json.dumps(item, sort_keys=True)),
                   sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": 1,
        "status": "completed",
        "source_kind": "GENERATED_RUN",
        "evidence_labels": ["generated_run"],
        "truth_status": "external_evidence_unverified",
        "belief_status": "not_committed",
        "repository": request["repository"],
        "commit_sha": request["commit_sha"],
        "paths": request["source_paths"],
        "operator_names": observed_operators,
        "registered_operator_names": registered,
        "run_id": request["run_id"],
        "seed": request["seed"],
        "seed_hash": request["seed_hash"],
        "controls": controls,
        "compute_limits": limits,
        "state_count": len(pool),
        "derivation_count": len(derivations),
        "max_dim": max((int(item.dim) for item in states), default=0),
        "kinds": sorted({str(item.kind) for item in states}),
        "state_signature_sha256": state_digest,
        "wall_seconds": round(time.monotonic() - started, 6),
        "provenance": provenance,
        "artifact": f"{request['run_id']}/result.json",
    }


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("fixed runner requires request, source directory and result paths")
    request_path, source_path, result_path = map(Path, sys.argv[1:])
    request = json.loads(request_path.read_text(encoding="utf-8"))
    result = execute(request, source_path)
    result_path.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()

