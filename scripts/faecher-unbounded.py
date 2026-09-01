#!/usr/bin/env python3
"""Budgeted, provenance-complete saturation experiment for the FAECHER grammar.

The default run has no structural dimension limit. Optional finite dimension
limits exist only for staged controls and are reported as such; exhaustion of a
bounded stage is never presented as termination of the unbounded grammar.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import resource
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

import grammar  # noqa: E402


COMMUTATIVE_OPERATORS = frozenset({"op_product"})


@dataclass(frozen=True)
class ComputeLimits:
    wall_seconds: float
    ram_mb: float
    node_cap: int
    edge_cap: int


class ComputeLimitReached(RuntimeError):
    def __init__(self, cause: str):
        super().__init__(cause)
        self.cause = cause


def rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return peak / (1024 * 1024)
    return peak / 1024


def event_key(operator: str, inputs: tuple, output: tuple) -> tuple:
    if operator in COMMUTATIVE_OPERATORS:
        inputs = tuple(sorted(inputs))
    return operator, inputs, output


def family(signature: tuple) -> tuple:
    return (signature[0], *signature[2:])


def binary_candidates(left: Any, right: Any) -> tuple[Any, ...]:
    """Return every registered binary operator that can pass its kind guard.

    This is scheduling only: each candidate still executes the canonical
    operator and all semantic compatibility checks remain inside grammar.py.
    Unknown future operators default to evaluation so the scheduler cannot
    silently narrow the registry.
    """
    candidates = []
    for operator in grammar.BINARY:
        name = operator.__name__
        if name == "op_product":
            eligible = (
                left.kind in (grammar.CYCLE, grammar.PRODUCT)
                and right.kind in (grammar.CYCLE, grammar.PRODUCT)
                and left.sym == right.sym
                and left.bc == right.bc
                and left.order == right.order
                and left.dual == right.dual
            )
        elif name == "op_fiber":
            eligible = (
                left.kind in (grammar.CYCLE, grammar.PRODUCT, grammar.BOUNDARY)
                and right.kind == grammar.CYCLE
                and left.sym == right.sym
                and left.bc == right.bc
                and left.order == right.order
                and left.dual == right.dual
            )
        elif name == "op_degenerate":
            eligible = (
                left.kind in (grammar.CYCLE, grammar.PRODUCT, grammar.BUNDLE, grammar.WEIGHT)
                and left.mult == 1
                and right.kind == grammar.SYMMETRY
                and bool(right.anti)
            )
        elif name == "op_exclude":
            eligible = (
                left.kind in (grammar.CYCLE, grammar.PRODUCT, grammar.BUNDLE, grammar.INTEGER, grammar.WEIGHT)
                and left.occ is None
                and right.kind == grammar.CARRIER
            )
        else:
            eligible = True
        if eligible:
            candidates.append(operator)
    return tuple(candidates)


def strongly_connected_cycles(nodes: set[tuple], events: list[dict[str, Any]]) -> list[list[tuple]]:
    adjacency: dict[tuple, set[tuple]] = {node: set() for node in nodes}
    for event in events:
        if len(event["inputs"]) == 1:
            adjacency[event["inputs"][0]].add(event["output"])

    index = 0
    stack: list[tuple] = []
    on_stack: set[tuple] = set()
    indices: dict[tuple, int] = {}
    lowlinks: dict[tuple, int] = {}
    components: list[list[tuple]] = []

    sys.setrecursionlimit(max(10_000, len(nodes) * 2 + 100))

    def visit(node: tuple) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in adjacency[node]:
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            if len(component) > 1 or node in adjacency[node]:
                components.append(component)

    for node in sorted(nodes):
        if node not in indices:
            visit(node)
    return components


def dimension_metrics(pool: dict[tuple, Any], events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    states_by_dimension: dict[int, set[tuple]] = defaultdict(set)
    for signature in pool:
        states_by_dimension[signature[1]].add(signature)

    events_by_dimension: dict[int, list[dict[str, Any]]] = defaultdict(list)
    events_by_output: dict[tuple, set[tuple]] = defaultdict(set)
    for event in events:
        events_by_dimension[event["output"][1]].append(event)
        events_by_output[event["output"]].add(event["key"])

    cycles = strongly_connected_cycles(set(pool), events)
    cycles_by_dimension = Counter()
    for component in cycles:
        dimensions = {signature[1] for signature in component}
        if len(dimensions) == 1:
            cycles_by_dimension[next(iter(dimensions))] += 1

    first_kind_dimension: dict[str, int] = {}
    first_operator_dimension: dict[str, int] = {}
    for dimension, signatures in states_by_dimension.items():
        for signature in signatures:
            first_kind_dimension[signature[0]] = min(dimension, first_kind_dimension.get(signature[0], dimension))
    for dimension, dimension_events in events_by_dimension.items():
        for event in dimension_events:
            operator = event["operator"]
            first_operator_dimension[operator] = min(dimension, first_operator_dimension.get(operator, dimension))

    metrics = {}
    previous_signatures: set[tuple] = set()
    previous_families: set[tuple] = set()
    previous_kinds: set[str] = set()
    max_dimension = max(states_by_dimension, default=0)
    for dimension in range(max_dimension + 1):
        signatures = states_by_dimension.get(dimension, set())
        families = {family(signature) for signature in signatures}
        kinds = {signature[0] for signature in signatures}
        dimension_events = events_by_dimension.get(dimension, [])
        operator_counts = Counter(event["operator"] for event in dimension_events)
        confluence_count = sum(
            len(events_by_output[signature]) >= 2 for signature in signatures
        )
        metrics[str(dimension)] = {
            "new_states": len(signatures),
            "kinds_present": sorted(kinds),
            "new_kinds_first_appearing": sorted(
                kind for kind in kinds if first_kind_dimension[kind] == dimension
            ),
            "new_operator_transitions": len(dimension_events),
            "operator_transition_counts": dict(sorted(operator_counts.items())),
            "operators_first_appearing": sorted(
                operator for operator in operator_counts
                if first_operator_dimension[operator] == dimension
            ),
            "confluent_states": confluence_count,
            "unary_cycle_components": cycles_by_dimension[dimension],
            "kinds_disappearing_from_previous_dimension": sorted(previous_kinds - kinds) if dimension else [],
            "structural_families_disappearing_from_previous_dimension": (
                len(previous_families - families) if dimension else 0
            ),
            "structural_families_new_vs_previous_dimension": (
                len(families - previous_families) if dimension else len(families)
            ),
        }
        previous_signatures = signatures
        previous_families = families
        previous_kinds = kinds
    return metrics


def run_saturation(dimension_limit: int | None, limits: ComputeLimits) -> dict[str, Any]:
    previous_maxdim = grammar.MAXDIM
    grammar.MAXDIM = dimension_limit
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    attempts = 0

    pool = {seed.structural_sig(): seed for seed in grammar.SEEDS}
    seed_signatures = set(pool)
    state_keys = list(pool)
    state_index = {signature: index for index, signature in enumerate(state_keys)}
    discovery_level = {signature: 0 for signature in state_keys}
    queue = deque(state_keys)
    events_by_key: dict[tuple, dict[str, Any]] = {}
    stop_cause = "QUEUE_EXHAUSTED"

    if len(pool) > limits.node_cap:
        raise ValueError("node cap is smaller than the exact seed set")

    def check_compute_limits() -> None:
        elapsed = time.monotonic() - started
        if elapsed >= limits.wall_seconds:
            raise ComputeLimitReached("WALL_CLOCK_BUDGET")
        if rss_mb() >= limits.ram_mb:
            raise ComputeLimitReached("RAM_BUDGET")

    def offer(operator: str, inputs: tuple, output_state: Any) -> None:
        if output_state is None:
            return
        output = output_state.structural_sig()
        if output in inputs:
            return
        key = event_key(operator, inputs, output)
        if key in events_by_key:
            return
        is_new = output not in pool
        if is_new and len(pool) >= limits.node_cap:
            raise ComputeLimitReached("NODE_CAP")
        if len(events_by_key) >= limits.edge_cap:
            raise ComputeLimitReached("EDGE_CAP")
        level = max(discovery_level[item] for item in inputs) + 1
        events_by_key[key] = {
            "operator": operator,
            "inputs": key[1],
            "output": output,
            "level": level,
            "key": key,
        }
        if is_new:
            pool[output] = output_state
            discovery_level[output] = level
            state_index[output] = len(state_keys)
            state_keys.append(output)
            queue.append(output)

    def apply(operator: Any, inputs: tuple, states: tuple) -> None:
        nonlocal attempts
        attempts += 1
        if attempts % 256 == 0:
            check_compute_limits()
        offer(operator.__name__, inputs, operator(*states))

    try:
        while queue:
            check_compute_limits()
            signature = queue.popleft()
            state = pool[signature]
            for operator in grammar.UNARY:
                apply(operator, (signature,), (state,))

            # Every ordered binary pair is evaluated exactly once, when its
            # highest-discovery-index member is processed. Product reversal is
            # normalized only at event identity, matching the audited core.
            index = state_index[signature]
            prior_keys = state_keys[: index + 1]
            for other_signature in prior_keys:
                other = pool[other_signature]
                for operator in binary_candidates(state, other):
                    apply(operator, (signature, other_signature), (state, other))
                if signature != other_signature:
                    for operator in binary_candidates(other, state):
                        apply(operator, (other_signature, signature), (other, state))
    except ComputeLimitReached as exc:
        stop_cause = exc.cause
    finally:
        grammar.MAXDIM = previous_maxdim

    elapsed = time.monotonic() - started
    events = list(events_by_key.values())
    if stop_cause == "QUEUE_EXHAUSTED" and dimension_limit is None:
        termination_class = "STRUCTURAL_TERMINATION"
        structural_termination_proven = True
    elif stop_cause == "QUEUE_EXHAUSTED":
        termination_class = "STAGED_BOUND_SATURATION"
        structural_termination_proven = False
    else:
        termination_class = "COMPUTATIONAL_TERMINATION"
        structural_termination_proven = False

    grammar_path = Path(grammar.__file__)
    runner_path = Path(__file__)
    structures = [
        {
            "signature": signature,
            "discovery_level": discovery_level[signature],
            "seed": signature in seed_signatures,
        }
        for signature in state_keys
    ]
    provenance = [
        {
            "operator": event["operator"],
            "inputs": event["inputs"],
            "output": event["output"],
            "level": event["level"],
        }
        for event in events
    ]
    return {
        "schema": "ckk.faecher-unbounded-experiment.v1",
        "started_at": started_at,
        "mode": "UNBOUNDED" if dimension_limit is None else "STAGED_DIMENSION_CONTROL",
        "dimension_limit": dimension_limit,
        "dimension_limit_role": "NONE" if dimension_limit is None else "STAGED_CONTROL_BOUND_NOT_STRUCTURAL_RESULT",
        "grammar_sha256": hashlib.sha256(grammar_path.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(runner_path.read_bytes()).hexdigest(),
        "seeds": [seed.structural_sig() for seed in grammar.SEEDS],
        "operators": {
            "unary": [operator.__name__ for operator in grammar.UNARY],
            "binary": [operator.__name__ for operator in grammar.BINARY],
        },
        "compute_limits": {
            "wall_seconds": limits.wall_seconds,
            "ram_mb": limits.ram_mb,
            "node_cap": limits.node_cap,
            "edge_cap": limits.edge_cap,
        },
        "termination": {
            "class": termination_class,
            "cause": stop_cause,
            "structural_termination_proven": structural_termination_proven,
            "queue_exhausted": not queue,
        },
        "observed": {
            "elapsed_seconds": elapsed,
            "peak_rss_mb": rss_mb(),
            "operator_attempts": attempts,
            "states": len(pool),
            "derivation_events": len(events),
            "pending_states": len(queue),
            "maximum_dimension": max(signature[1] for signature in pool),
        },
        "dimension_metrics": dimension_metrics(pool, events),
        "structures": structures,
        "derivation_events": provenance,
    }


def json_safe(value: Any) -> Any:
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = json_safe(payload)
    if path.suffix == ".gz":
        with path.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as compressed:
                with io.TextIOWrapper(compressed, encoding="utf-8") as text:
                    json.dump(safe, text, sort_keys=True, separators=(",", ":"))
    else:
        path.write_text(json.dumps(safe, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: result[key]
        for key in (
            "schema", "started_at", "mode", "dimension_limit", "dimension_limit_role",
            "grammar_sha256", "runner_sha256", "seeds", "operators", "compute_limits", "termination",
            "observed", "dimension_metrics",
        )
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-dimension", type=int, default=None)
    parser.add_argument("--wall-seconds", type=float, default=30.0)
    parser.add_argument("--ram-mb", type=float, default=1024.0)
    parser.add_argument("--node-cap", type=int, default=20_000)
    parser.add_argument("--edge-cap", type=int, default=250_000)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_dimension is not None and args.max_dimension < 1:
        raise SystemExit("max dimension must be positive")
    if min(args.wall_seconds, args.ram_mb, args.node_cap, args.edge_cap) <= 0:
        raise SystemExit("all compute budgets must be positive")

    result = run_saturation(
        args.max_dimension,
        ComputeLimits(args.wall_seconds, args.ram_mb, args.node_cap, args.edge_cap),
    )
    write_json(args.output, result)
    short = summary(result)
    short["provenance_artifact"] = {
        "path": str(args.output),
        "sha256": artifact_sha256(args.output),
        "bytes": args.output.stat().st_size,
    }
    write_json(args.summary_output, short)
    print(json.dumps(json_safe(short), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
