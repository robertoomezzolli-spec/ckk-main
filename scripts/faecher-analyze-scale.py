#!/usr/bin/env python3
"""Reconstruct longitudinal FAECHER scale metrics from the exact checkpoint."""

from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "ckk_snapshot" / "ckk" / "gen"
sys.path.insert(0, str(GEN))

from stream_expand import ComputeLimits, open_engine  # noqa: E402


NULL_KEY = "__NULL__"


def scalar(row: tuple) -> tuple:
    kind, dim, order, sym, sq, anti, mult, bc, dual, occ = row
    return (
        kind,
        dim,
        order,
        str(sym),
        str(sq),
        str(None if anti is None else bool(anti)),
        mult,
        str(bc),
        dual,
        str(occ),
    )


def virtual_quotient_counts(connection: sqlite3.Connection, through_level: int) -> Counter:
    counts: Counter = Counter()
    rows = connection.execute(
        "SELECT kind,dim,ord,sym,sq,anti,mult,bc,dual,occ,count(*) "
        "FROM states WHERE born_level<=? GROUP BY kind,dim,ord,sym,sq,anti,mult,bc,dual,occ",
        (through_level,),
    )
    for *values, count in rows:
        counts[scalar(tuple(values))] += count

    segments = connection.execute(
        "SELECT level,ord,sym_key,bc_key,dual FROM virtual_product_segments "
        "WHERE level<=? ORDER BY level,id",
        (through_level,),
    )
    for level, order, sym_key, bc_key, dual in segments:
        sym = None if sym_key == NULL_KEY else sym_key
        bc = None if bc_key == NULL_KEY else bc_key
        types: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        for dim, mult, occ, born, count in connection.execute(
            "SELECT dim,mult,occ,born_level,count(*) FROM states "
            "WHERE kind IN ('CYCLE','PRODUCT') AND born_level<? AND ord=? "
            "AND sym IS ? AND bc IS ? AND dual=? GROUP BY dim,mult,occ,born_level",
            (level, order, sym, bc, dual),
        ):
            key = (dim, mult, occ)
            types[key][0] += count
            if born < level - 1:
                types[key][1] += count
        keys = sorted(types, key=lambda item: (item[0], item[1], -10**30 if item[2] is None else item[2]))
        for left_index, left in enumerate(keys):
            for right in keys[left_index:]:
                left_total, left_old = types[left]
                right_total, right_old = types[right]
                if left == right:
                    pair_count = (
                        left_total * (left_total + 1) // 2
                        - left_old * (left_old + 1) // 2
                    )
                else:
                    pair_count = left_total * right_total - left_old * right_old
                if not pair_count:
                    continue
                left_dim, left_mult, left_occ = left
                right_dim, right_mult, right_occ = right
                signature = (
                    "PRODUCT",
                    left_dim + right_dim,
                    order,
                    str(sym),
                    "None",
                    "None",
                    max(left_mult, right_mult),
                    str(bc),
                    dual,
                    str(left_occ if left_occ == right_occ else None),
                )
                counts[signature] += pair_count
    return counts


def product_pair_rank(i: int, j: int, total: int, old: int) -> int:
    if i < old:
        return i * (total - old) + (j - old)
    offset = i - old
    width = total - old
    prior = old * width + offset * width - offset * (offset - 1) // 2
    return prior + (j - i)


def maximum_dimension_witness(engine) -> list[dict]:
    connection = engine.connection
    cycle = connection.execute(
        "SELECT s.id FROM states s JOIN derivations d ON d.output=s.id "
        "WHERE s.born_level=1 AND s.kind='CYCLE' AND s.dim=1 "
        "AND d.operator='op_close' ORDER BY s.ord,s.id LIMIT 1"
    ).fetchone()[0]
    path = [{"level": 1, "state_id": cycle, "dim": 1, "operator": "op_close"}]
    parent = cycle
    for level in range(2, 6):
        row = connection.execute(
            "SELECT s.id,s.dim FROM derivations d JOIN states s ON s.id=d.output "
            "WHERE d.operator='op_product' AND d.input_a=? AND d.input_b=? "
            "AND s.born_level=? ORDER BY s.id LIMIT 1",
            (parent, parent, level),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"missing self-product witness at level {level}")
        parent = row[0]
        path.append(
            {
                "level": level,
                "state_id": parent,
                "dim": row[1],
                "operator": "op_product",
                "parents": [path[-1]["state_id"], path[-1]["state_id"]],
            }
        )

    parent_row = connection.execute(
        "SELECT ord,coalesce(sym,?),coalesce(bc,?),dual FROM states WHERE id=?",
        (NULL_KEY, NULL_KEY, parent),
    ).fetchone()
    segment = connection.execute(
        "SELECT id,level,ord,sym_key,bc_key,dual,member_count,old_member_count,"
        "child_count,virtual_start FROM virtual_product_segments "
        "WHERE level=6 AND ord=? AND sym_key=? AND bc_key=? AND dual=?",
        parent_row,
    ).fetchone()
    members = engine._product_group_members((*segment, 0))
    index = members.index(parent)
    rank = product_pair_rank(index, index, segment[6], segment[7])
    virtual_id = segment[9] - rank
    virtual = engine._load_ref(virtual_id)
    path.append(
        {
            "level": 6,
            "state_id": virtual_id,
            "dim": virtual.dim,
            "operator": "op_product",
            "parents": [parent, parent],
            "segment": segment[0],
            "rank": rank,
        }
    )
    return path


def analyze(database: Path) -> dict:
    engine = open_engine(database, ComputeLimits(3600, 100_000, 1))
    try:
        connection = engine.connection
        completed = int(engine._meta("completed_level", "0"))
        level_rows = {row["level"]: row for row in engine.level_rows()}
        first_kinds: dict[str, int] = {}
        first_operators: dict[str, int] = {}
        output = []
        previous_frontier_kinds: set[str] = set()
        previous_quotient: set[tuple] = set()
        for level in range(1, completed + 1):
            frontier_kinds = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT kind FROM states WHERE born_level=?", (level,)
                )
            }
            if connection.execute(
                "SELECT 1 FROM virtual_product_segments WHERE level=? LIMIT 1", (level,)
            ).fetchone():
                frontier_kinds.add("PRODUCT")
            for kind in frontier_kinds:
                first_kinds.setdefault(kind, level)

            operators = Counter(
                dict(
                    connection.execute(
                        "SELECT operator,count(*) FROM derivations WHERE first_level=? "
                        "GROUP BY operator",
                        (level,),
                    )
                )
            )
            virtual_products = connection.execute(
                "SELECT coalesce(sum(child_count),0) FROM virtual_product_segments WHERE level=?",
                (level,),
            ).fetchone()[0]
            operators["op_product"] += virtual_products
            for operator in operators:
                if operators[operator]:
                    first_operators.setdefault(operator, level)

            confluences = connection.execute(
                "SELECT count(*) FROM (SELECT output FROM derivations WHERE first_level<=? "
                "GROUP BY output HAVING count(*)>1)",
                (level,),
            ).fetchone()[0]
            cycles = connection.execute(
                "SELECT count(*) FROM derivations a JOIN derivations b ON "
                "a.input_b=0 AND b.input_b=0 AND a.input_a=b.output "
                "AND a.output=b.input_a AND a.id<b.id "
                "WHERE a.first_level<=? AND b.first_level<=?",
                (level, level),
            ).fetchone()[0]
            path_motifs = connection.execute(
                "SELECT count(*) FROM (SELECT d.operator,a.kind,b.kind,o.kind "
                "FROM derivations d JOIN states a ON a.id=d.input_a "
                "LEFT JOIN states b ON b.id=d.input_b JOIN states o ON o.id=d.output "
                "WHERE d.first_level<=? GROUP BY d.operator,a.kind,b.kind,o.kind)",
                (level,),
            ).fetchone()[0]
            quotient_counts = virtual_quotient_counts(connection, level)
            quotient = set(quotient_counts)
            row = dict(level_rows[level])
            row.update(
                {
                    "frontier_kinds": sorted(frontier_kinds),
                    "new_kinds_first_appearing": sorted(
                        kind for kind in frontier_kinds if first_kinds[kind] == level
                    ),
                    "kinds_disappearing_from_previous_frontier": sorted(
                        previous_frontier_kinds - frontier_kinds
                    ),
                    "operator_transitions_added": sum(operators.values()),
                    "operator_transition_counts": dict(sorted(operators.items())),
                    "operators_first_appearing": sorted(
                        op for op, count in operators.items()
                        if count and first_operators[op] == level
                    ),
                    "confluent_states_cumulative": confluences,
                    "cycles_cumulative": cycles,
                    "immediate_operator_path_motifs_cumulative": path_motifs,
                    "quotient_structural_states_cumulative": len(quotient),
                    "new_quotient_signatures": len(quotient - previous_quotient),
                    "repeated_structural_motif_classes": sum(
                        count > 1 for count in quotient_counts.values()
                    ),
                }
            )
            output.append(row)
            previous_frontier_kinds = frontier_kinds
            previous_quotient = quotient

        phase_rows = {}
        for level, phase, attempted, successful, unique_states, duplicates in connection.execute(
            "SELECT level,phase,attempted,successful,unique_states,duplicate_states "
            "FROM phase_progress ORDER BY level,phase"
        ):
            phase_rows.setdefault(str(level), {})[phase.split(":", 1)[1]] = {
                "applications_attempted": attempted,
                "successful_applications": successful,
                "unique_states_first_inserted": unique_states,
                "duplicate_states": duplicates,
            }

        return {
            "schema": "ckk.faecher-scale-analysis.v1",
            "completed_level": completed,
            "termination": {
                "class": engine._meta("termination_class"),
                "cause": engine._meta("termination_cause"),
            },
            "levels": output,
            "operators_by_level": phase_rows,
            "maximum_dimension_witness": maximum_dimension_witness(engine),
            "database_bytes": database.stat().st_size,
        }
    finally:
        engine.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.database)
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
