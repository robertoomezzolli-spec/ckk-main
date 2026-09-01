"""Disk-backed exact level expansion for the provenance-bearing FAECHER grammar.

The grammar operators remain the semantic authority.  This module changes the
representation and scheduling only:

* historical ``Struct.sig()`` trees are hash-consed into exact state IDs;
* derivations contain state references instead of copied recursive tuples;
* candidate rows stream from SQLite and are checkpointed in bounded batches;
* deterministic semi-naive evaluation avoids re-running old/old pairs;
* only ``op_product`` uses unordered pairs, because its implementation is
  symmetric and its historical signature sorts its two parts.

By induction, ``(scalar signature, multiset of canonical direct-part IDs)`` is
an exact interning key for ``Struct.sig()`` equality.  No digest collision is
involved in state identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import resource
import shutil
import sqlite3
import sys
import time
from typing import Any, Iterator

import grammar


COMMUTATIVE_OPERATORS = frozenset({"op_product"})
KNOWN_BINARY = frozenset(
    {"op_product", "op_fiber", "op_degenerate", "op_exclude"}
)


@dataclass(frozen=True)
class PartRef:
    _state_id: int


@dataclass(frozen=True)
class StateRef:
    _state_id: int
    kind: str
    dim: int = 0
    order: int = 0
    parts: tuple[PartRef, ...] = ()
    label: str = ""
    mult: int = 1
    sq: int | None = None
    anti: bool | None = None
    sym: str | None = None
    bc: str | None = None
    dual: int = 0
    occ: int | None = None


@dataclass(frozen=True)
class ComputeLimits:
    wall_seconds: float
    ram_mb: float
    minimum_free_disk_mb: float
    node_cap: int | None = None
    derivation_cap: int | None = None


class ComputeLimitReached(RuntimeError):
    def __init__(self, cause: str):
        super().__init__(cause)
        self.cause = cause


def rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def scalar_signature(state: Any) -> tuple:
    """The exact scalar prefix used by historical ``Struct.sig()``."""
    return (
        state.kind,
        state.dim,
        state.order,
        str(state.sym),
        str(state.sq),
        str(state.anti),
        state.mult,
        str(state.bc),
        state.dual,
        str(state.occ),
    )


def state_key(state: Any, part_ids: tuple[int, ...]) -> bytes:
    """Collision-free key inside one canonical state database."""
    value = (*scalar_signature(state), sorted(part_ids))
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS states (
    id INTEGER PRIMARY KEY,
    state_key BLOB NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    dim INTEGER NOT NULL,
    ord INTEGER NOT NULL,
    label TEXT NOT NULL,
    mult INTEGER NOT NULL,
    sq INTEGER,
    anti INTEGER,
    sym TEXT,
    bc TEXT,
    dual INTEGER NOT NULL,
    occ INTEGER,
    part_a INTEGER,
    part_b INTEGER,
    part_count INTEGER NOT NULL,
    born_level INTEGER NOT NULL,
    FOREIGN KEY(part_a) REFERENCES states(id),
    FOREIGN KEY(part_b) REFERENCES states(id)
);
CREATE INDEX IF NOT EXISTS states_level_idx ON states(born_level, id);
CREATE INDEX IF NOT EXISTS states_product_idx
    ON states(kind, ord, sym, bc, dual, born_level, id);
CREATE INDEX IF NOT EXISTS states_degenerate_idx
    ON states(kind, mult, born_level, id);
CREATE INDEX IF NOT EXISTS states_exclude_idx
    ON states(kind, occ, born_level, id);
CREATE TABLE IF NOT EXISTS derivations (
    id INTEGER PRIMARY KEY,
    operator TEXT NOT NULL,
    input_a INTEGER NOT NULL,
    input_b INTEGER NOT NULL DEFAULT 0,
    output INTEGER NOT NULL,
    first_level INTEGER NOT NULL,
    UNIQUE(operator, input_a, input_b, output),
    FOREIGN KEY(input_a) REFERENCES states(id),
    FOREIGN KEY(output) REFERENCES states(id)
);
CREATE INDEX IF NOT EXISTS derivations_output_idx ON derivations(output);
CREATE INDEX IF NOT EXISTS derivations_operator_idx ON derivations(operator);
CREATE TABLE IF NOT EXISTS phase_progress (
    level INTEGER NOT NULL,
    phase TEXT NOT NULL,
    cursor_a INTEGER NOT NULL DEFAULT 0,
    cursor_b INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    attempted INTEGER NOT NULL DEFAULT 0,
    successful INTEGER NOT NULL DEFAULT 0,
    idempotent INTEGER NOT NULL DEFAULT 0,
    unique_states INTEGER NOT NULL DEFAULT 0,
    duplicate_states INTEGER NOT NULL DEFAULT 0,
    derivations_added INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds REAL NOT NULL DEFAULT 0,
    PRIMARY KEY(level, phase)
);
CREATE TABLE IF NOT EXISTS level_stats (
    level INTEGER PRIMARY KEY,
    total_states INTEGER NOT NULL,
    new_states INTEGER NOT NULL,
    max_dim INTEGER NOT NULL,
    derivations INTEGER NOT NULL,
    logical_candidate_pairs INTEGER NOT NULL,
    streamed_operator_candidates INTEGER NOT NULL,
    duplicates_rejected INTEGER NOT NULL,
    peak_rss_mb REAL NOT NULL,
    wall_seconds REAL NOT NULL,
    checkpoint_path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS virtual_product_segments (
    id INTEGER PRIMARY KEY,
    level INTEGER NOT NULL,
    ord INTEGER NOT NULL,
    sym_key TEXT NOT NULL,
    bc_key TEXT NOT NULL,
    dual INTEGER NOT NULL,
    member_count INTEGER NOT NULL,
    old_member_count INTEGER NOT NULL,
    child_count INTEGER NOT NULL,
    virtual_start INTEGER NOT NULL,
    maximum_child_dimension INTEGER NOT NULL,
    UNIQUE(level, ord, sym_key, bc_key, dual)
);
"""


class StreamingExpansion:
    def __init__(
        self,
        database: Path,
        limits: ComputeLimits,
        *,
        batch_size: int = 2_000,
        sqlite_cache_mb: int = 64,
        symbolic_product_threshold: int | None = None,
    ) -> None:
        self.database = database.resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.limits = limits
        self.batch_size = batch_size
        self.symbolic_product_threshold = symbolic_product_threshold
        self.started = time.monotonic()
        self.connection = sqlite3.connect(self.database, timeout=120)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA temp_store=FILE")
        self.connection.execute(f"PRAGMA cache_size={-sqlite_cache_mb * 1024}")
        self.connection.executescript(SCHEMA)
        self.connection.commit()
        self._operators = {
            op.__name__: op for op in grammar.UNARY + grammar.BINARY
        }
        self._validate_registry()
        self._initialize()

    def close(self) -> None:
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.connection.close()

    def _validate_registry(self) -> None:
        names = [op.__name__ for op in grammar.UNARY + grammar.BINARY]
        if len(names) != len(set(names)):
            raise ValueError("operator names must be unique")
        if grammar.MAXDIM is not None:
            raise ValueError("streaming scale run requires grammar.MAXDIM=None")

    def _meta(self, key: str, default: str | None = None) -> str | None:
        row = self.connection.execute(
            "SELECT value FROM meta WHERE key=?", (key,)
        ).fetchone()
        return row[0] if row else default

    def _set_meta(self, key: str, value: Any) -> None:
        self.connection.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )

    def _initialize(self) -> None:
        schema_version = self._meta("schema_version")
        if schema_version is not None:
            if schema_version != "1":
                raise ValueError(f"unsupported database schema {schema_version}")
            return
        self.connection.execute("BEGIN IMMEDIATE")
        self._set_meta("schema_version", 1)
        self._set_meta("completed_level", 0)
        self._set_meta("termination_class", "RUNNING")
        self._set_meta("termination_cause", "NONE")
        for seed in grammar.SEEDS:
            self._intern(seed, (), 0)
        self.connection.commit()

    @lru_cache(maxsize=8_192)
    def _load_ref(self, state_id: int) -> StateRef:
        if state_id < 0:
            return self._load_virtual_product_ref(state_id)
        row = self.connection.execute(
            "SELECT kind,dim,ord,label,mult,sq,anti,sym,bc,dual,occ,"
            "part_a,part_b,part_count FROM states WHERE id=?",
            (state_id,),
        ).fetchone()
        if row is None:
            raise KeyError(state_id)
        part_ids = row[11:13][: row[13]]
        return StateRef(
            state_id,
            row[0],
            row[1],
            row[2],
            tuple(PartRef(item) for item in part_ids),
            row[3],
            row[4],
            row[5],
            None if row[6] is None else bool(row[6]),
            row[7],
            row[8],
            row[9],
            row[10],
        )

    def _product_group_members(self, segment: tuple) -> list[int]:
        _, level, order, sym_key, bc_key, dual, *_ = segment
        sym = None if sym_key == "__NULL__" else sym_key
        bc = None if bc_key == "__NULL__" else bc_key
        return [
            row[0]
            for row in self.connection.execute(
                "SELECT id FROM states WHERE kind IN ('CYCLE','PRODUCT') "
                "AND born_level<=? AND ord=? AND sym IS ? AND bc IS ? AND dual=? "
                "ORDER BY id",
                (level - 1, order, sym, bc, dual),
            )
        ]

    @staticmethod
    def _unrank_frontier_pair(
        rank: int, member_count: int, old_count: int
    ) -> tuple[int, int]:
        """Unrank lexicographic i<=j pairs with at least one frontier member."""
        low = 0
        high = member_count
        while low < high:
            middle = (low + high) // 2
            if middle < old_count:
                prior = middle * (member_count - old_count)
            else:
                prior = old_count * (member_count - old_count)
                width = member_count - old_count
                offset = middle - old_count
                prior += offset * width - offset * (offset - 1) // 2
            if prior <= rank:
                low = middle + 1
            else:
                high = middle
        i = low - 1
        if i < old_count:
            prior = i * (member_count - old_count)
            j = old_count + rank - prior
        else:
            offset = i - old_count
            width = member_count - old_count
            prior = old_count * width + offset * width - offset * (offset - 1) // 2
            j = i + rank - prior
        if not (0 <= i <= j < member_count):
            raise IndexError(rank)
        return i, j

    def _load_virtual_product_ref(self, state_id: int) -> StateRef:
        segment = self.connection.execute(
            "SELECT id,level,ord,sym_key,bc_key,dual,member_count,old_member_count,"
            "child_count,virtual_start,maximum_child_dimension "
            "FROM virtual_product_segments WHERE virtual_start>=? "
            "AND virtual_start-child_count+1<=? ORDER BY virtual_start LIMIT 1",
            (state_id, state_id),
        ).fetchone()
        if segment is None:
            raise KeyError(state_id)
        rank = segment[9] - state_id
        left_index, right_index = self._unrank_frontier_pair(
            rank, segment[6], segment[7]
        )
        members = self._product_group_members(segment)
        left = self._load_ref(members[left_index])
        right = self._load_ref(members[right_index])
        output = grammar.op_product(left, right)
        if output is None:
            raise RuntimeError("virtual product segment violated canonical operator")
        return StateRef(
            state_id,
            output.kind,
            output.dim,
            output.order,
            tuple(PartRef(item._state_id) for item in output.parts),
            output.label,
            output.mult,
            output.sq,
            output.anti,
            output.sym,
            output.bc,
            output.dual,
            output.occ,
        )

    def _intern(
        self, state: Any, part_ids: tuple[int, ...], born_level: int
    ) -> tuple[int, bool]:
        ordered_parts = tuple(sorted(part_ids))
        if len(ordered_parts) > 2:
            raise ValueError("registered grammar produced more than two direct parts")
        key = state_key(state, ordered_parts)
        values = (
            key,
            state.kind,
            state.dim,
            state.order,
            state.label,
            state.mult,
            state.sq,
            None if state.anti is None else int(state.anti),
            state.sym,
            state.bc,
            state.dual,
            state.occ,
            ordered_parts[0] if ordered_parts else None,
            ordered_parts[1] if len(ordered_parts) > 1 else None,
            len(ordered_parts),
            born_level,
        )
        before = self.connection.total_changes
        self.connection.execute(
            "INSERT OR IGNORE INTO states("
            "state_key,kind,dim,ord,label,mult,sq,anti,sym,bc,dual,occ,"
            "part_a,part_b,part_count,born_level) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            values,
        )
        inserted = self.connection.total_changes > before
        row = self.connection.execute(
            "SELECT id FROM states WHERE state_key=?", (key,)
        ).fetchone()
        if row is None:
            raise RuntimeError("state interning failed")
        return row[0], inserted

    def _check_limits(self) -> None:
        if time.monotonic() - self.started >= self.limits.wall_seconds:
            raise ComputeLimitReached("WALL_CLOCK_BUDGET")
        if rss_mb() >= self.limits.ram_mb:
            raise ComputeLimitReached("RAM_WATERMARK")
        free_mb = shutil.disk_usage(self.database.parent).free / (1024 * 1024)
        if free_mb <= self.limits.minimum_free_disk_mb:
            raise ComputeLimitReached("DISK_WATERMARK")
        if self.limits.node_cap is not None:
            states = self.connection.execute("SELECT count(*) FROM states").fetchone()[0]
            if states >= self.limits.node_cap:
                raise ComputeLimitReached("NODE_CAP")
        if self.limits.derivation_cap is not None:
            edges = self.connection.execute(
                "SELECT count(*) FROM derivations"
            ).fetchone()[0]
            if edges >= self.limits.derivation_cap:
                raise ComputeLimitReached("DERIVATION_CAP")

    def _progress(self, level: int, phase: str) -> dict[str, Any]:
        self.connection.execute(
            "INSERT OR IGNORE INTO phase_progress(level,phase) VALUES(?,?)",
            (level, phase),
        )
        row = self.connection.execute(
            "SELECT cursor_a,cursor_b,done,attempted,successful,idempotent,"
            "unique_states,duplicate_states,derivations_added,elapsed_seconds "
            "FROM phase_progress WHERE level=? AND phase=?",
            (level, phase),
        ).fetchone()
        keys = (
            "cursor_a",
            "cursor_b",
            "done",
            "attempted",
            "successful",
            "idempotent",
            "unique_states",
            "duplicate_states",
            "derivations_added",
            "elapsed_seconds",
        )
        return dict(zip(keys, row))

    def _save_progress(self, level: int, phase: str, progress: dict) -> None:
        self.connection.execute(
            "UPDATE phase_progress SET cursor_a=?,cursor_b=?,done=?,attempted=?,"
            "successful=?,idempotent=?,unique_states=?,duplicate_states=?,"
            "derivations_added=?,elapsed_seconds=? WHERE level=? AND phase=?",
            (
                progress["cursor_a"],
                progress["cursor_b"],
                progress["done"],
                progress["attempted"],
                progress["successful"],
                progress["idempotent"],
                progress["unique_states"],
                progress["duplicate_states"],
                progress["derivations_added"],
                progress["elapsed_seconds"],
                level,
                phase,
            ),
        )

    def _unary_rows(
        self, frontier: int, cursor: int
    ) -> Iterator[tuple[int, int]]:
        rows = self.connection.execute(
            "SELECT id,0 FROM states WHERE born_level=? AND id>? "
            "ORDER BY id LIMIT ?",
            (frontier, cursor, self.batch_size),
        )
        yield from rows

    def _binary_sql(self, operator: str) -> str:
        common = (
            "a.born_level<=:frontier AND b.born_level<=:frontier AND "
            "(a.born_level=:frontier OR b.born_level=:frontier) AND "
            "(a.id>:cursor_a OR (a.id=:cursor_a AND b.id>:cursor_b))"
        )
        if operator == "op_product":
            guard = (
                "a.kind IN ('CYCLE','PRODUCT') AND "
                "b.kind IN ('CYCLE','PRODUCT') AND a.ord=b.ord AND "
                "a.sym IS b.sym AND a.bc IS b.bc AND a.dual=b.dual AND a.id<=b.id"
            )
        elif operator == "op_fiber":
            guard = (
                "a.kind IN ('CYCLE','PRODUCT','BOUNDARY') AND b.kind='CYCLE' AND "
                "a.ord=b.ord AND a.sym IS b.sym AND a.bc IS b.bc AND a.dual=b.dual"
            )
        elif operator == "op_degenerate":
            guard = (
                "a.kind IN ('CYCLE','PRODUCT','BUNDLE','WEIGHT') AND a.mult=1 AND "
                "b.kind='SYMMETRY' AND b.anti=1"
            )
        elif operator == "op_exclude":
            guard = (
                "a.kind IN ('CYCLE','PRODUCT','BUNDLE','INTEGER','WEIGHT') AND "
                "a.occ IS NULL AND b.kind='CARRIER'"
            )
        else:
            guard = "a.id<=b.id" if operator in COMMUTATIVE_OPERATORS else "1=1"
        return (
            "SELECT a.id,b.id FROM states a JOIN states b ON "
            + guard
            + " WHERE "
            + common
            + " ORDER BY a.id,b.id LIMIT :batch"
        )

    def _binary_rows(
        self, operator: str, frontier: int, cursor_a: int, cursor_b: int
    ) -> Iterator[tuple[int, int]]:
        rows = self.connection.execute(
            self._binary_sql(operator),
            {
                "frontier": frontier,
                "cursor_a": cursor_a,
                "cursor_b": cursor_b,
                "batch": self.batch_size,
            },
        )
        yield from rows

    def _eligible_product_count(self, frontier: int) -> int:
        total = 0
        for count, old_count in self.connection.execute(
            "SELECT count(*),sum(CASE WHEN born_level<? THEN 1 ELSE 0 END) "
            "FROM states WHERE kind IN ('CYCLE','PRODUCT') AND born_level<=? "
            "GROUP BY ord,coalesce(sym,'__NULL__'),coalesce(bc,'__NULL__'),dual",
            (frontier, frontier),
        ):
            old_count = old_count or 0
            total += count * (count + 1) // 2 - old_count * (old_count + 1) // 2
        return total

    def _run_symbolic_product(self, level: int, phase: str) -> None:
        progress = self._progress(level, phase)
        self.connection.commit()
        if progress["done"]:
            return
        frontier = level - 1
        tick = time.perf_counter()
        groups = list(
            self.connection.execute(
                "SELECT ord,coalesce(sym,'__NULL__'),coalesce(bc,'__NULL__'),dual,"
                "count(*),sum(CASE WHEN born_level<? THEN 1 ELSE 0 END),max(dim) "
                "FROM states WHERE kind IN ('CYCLE','PRODUCT') AND born_level<=? "
                "GROUP BY ord,coalesce(sym,'__NULL__'),coalesce(bc,'__NULL__'),dual "
                "ORDER BY ord,2,3,dual",
                (frontier, frontier),
            )
        )
        next_virtual = self.connection.execute(
            "SELECT coalesce(min(virtual_start-child_count),0)-1 "
            "FROM virtual_product_segments"
        ).fetchone()[0]
        self.connection.execute("BEGIN IMMEDIATE")
        total = 0
        for order, sym_key, bc_key, dual, count, old_count, max_dim in groups:
            old_count = old_count or 0
            children = count * (count + 1) // 2 - old_count * (old_count + 1) // 2
            if not children:
                continue
            self.connection.execute(
                "INSERT OR IGNORE INTO virtual_product_segments("
                "level,ord,sym_key,bc_key,dual,member_count,old_member_count,"
                "child_count,virtual_start,maximum_child_dimension) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    level,
                    order,
                    sym_key,
                    bc_key,
                    dual,
                    count,
                    old_count,
                    children,
                    next_virtual,
                    max_dim * 2,
                ),
            )
            next_virtual -= children
            total += children
        progress["attempted"] = total
        progress["successful"] = total
        progress["unique_states"] = total
        progress["derivations_added"] = total
        progress["elapsed_seconds"] += time.perf_counter() - tick
        progress["done"] = 1
        self._save_progress(level, phase, progress)
        self.connection.commit()

    def _offer(
        self,
        operator_name: str,
        inputs: tuple[StateRef, ...],
        level: int,
        progress: dict[str, Any],
    ) -> None:
        progress["attempted"] += 1
        output = self._operators[operator_name](*inputs)
        if output is None:
            return
        progress["successful"] += 1
        part_ids = tuple(part._state_id for part in output.parts)
        output_id, inserted = self._intern(output, part_ids, level)
        input_ids = tuple(item._state_id for item in inputs)
        if output_id in input_ids:
            progress["idempotent"] += 1
            return
        if inserted:
            progress["unique_states"] += 1
            self._load_ref.cache_clear()
        else:
            progress["duplicate_states"] += 1
        edge_inputs = input_ids
        if operator_name in COMMUTATIVE_OPERATORS:
            edge_inputs = tuple(sorted(edge_inputs))
        input_b = edge_inputs[1] if len(edge_inputs) == 2 else 0
        before = self.connection.total_changes
        self.connection.execute(
            "INSERT OR IGNORE INTO derivations(operator,input_a,input_b,output,first_level) "
            "VALUES(?,?,?,?,?)",
            (operator_name, edge_inputs[0], input_b, output_id, level),
        )
        if self.connection.total_changes > before:
            progress["derivations_added"] += 1

    def _run_phase(self, level: int, phase: str, operator_name: str) -> None:
        if operator_name == "op_product" and self.symbolic_product_threshold is not None:
            eligible = self._eligible_product_count(level - 1)
            if eligible >= self.symbolic_product_threshold:
                self._run_symbolic_product(level, phase)
                return
        progress = self._progress(level, phase)
        self.connection.commit()
        if progress["done"]:
            return
        frontier = level - 1
        unary = operator_name in {op.__name__ for op in grammar.UNARY}
        while True:
            self._check_limits()
            tick = time.perf_counter()
            if unary:
                rows = list(self._unary_rows(frontier, progress["cursor_a"]))
            else:
                rows = list(
                    self._binary_rows(
                        operator_name,
                        frontier,
                        progress["cursor_a"],
                        progress["cursor_b"],
                    )
                )
            if not rows:
                progress["done"] = 1
                self._save_progress(level, phase, progress)
                self.connection.commit()
                return
            self.connection.execute("BEGIN IMMEDIATE")
            for input_a, input_b in rows:
                inputs = (self._load_ref(input_a),)
                if input_b:
                    inputs += (self._load_ref(input_b),)
                self._offer(operator_name, inputs, level, progress)
                progress["cursor_a"] = input_a
                progress["cursor_b"] = input_b
            progress["elapsed_seconds"] += time.perf_counter() - tick
            self._save_progress(level, phase, progress)
            self.connection.commit()

    def _complete_level(self, level: int) -> dict[str, Any]:
        material_states = self.connection.execute(
            "SELECT count(*) FROM states"
        ).fetchone()[0]
        virtual_states = self.connection.execute(
            "SELECT coalesce(sum(child_count),0) FROM virtual_product_segments"
        ).fetchone()[0]
        total_states = material_states + virtual_states
        material_new = self.connection.execute(
            "SELECT count(*) FROM states WHERE born_level=?", (level,)
        ).fetchone()[0]
        virtual_new = self.connection.execute(
            "SELECT coalesce(sum(child_count),0) FROM virtual_product_segments WHERE level=?",
            (level,),
        ).fetchone()[0]
        new_states = material_new + virtual_new
        pool_before = total_states - new_states
        material_max = self.connection.execute("SELECT max(dim) FROM states").fetchone()[0]
        virtual_max = self.connection.execute(
            "SELECT coalesce(max(maximum_child_dimension),0) FROM virtual_product_segments"
        ).fetchone()[0]
        max_dim = max(material_max, virtual_max)
        material_derivations = self.connection.execute(
            "SELECT count(*) FROM derivations"
        ).fetchone()[0]
        virtual_derivations = self.connection.execute(
            "SELECT coalesce(sum(child_count),0) FROM virtual_product_segments"
        ).fetchone()[0]
        derivations = material_derivations + virtual_derivations
        phase = self.connection.execute(
            "SELECT coalesce(sum(attempted),0),coalesce(sum(duplicate_states),0),"
            "coalesce(sum(elapsed_seconds),0) FROM phase_progress WHERE level=?",
            (level,),
        ).fetchone()
        row = {
            "level": level,
            "total_states": total_states,
            "new_states": new_states,
            "max_dim": max_dim,
            "derivations": derivations,
            "logical_candidate_pairs": pool_before * pool_before,
            "streamed_operator_candidates": phase[0],
            "duplicates_rejected": phase[1],
            "peak_rss_mb": rss_mb(),
            "wall_seconds": phase[2],
            "checkpoint_path": str(self.database),
        }
        self.connection.execute("BEGIN IMMEDIATE")
        self.connection.execute(
            "INSERT OR REPLACE INTO level_stats VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            tuple(row.values()),
        )
        self._set_meta("completed_level", level)
        self._set_meta("termination_class", "RUNNING")
        self._set_meta("termination_cause", "NONE")
        self.connection.commit()
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        return row

    def run_to_level(self, requested_level: int) -> dict[str, Any]:
        completed = int(self._meta("completed_level", "0"))
        rows = []
        try:
            for level in range(completed + 1, requested_level + 1):
                prior_virtual = self.connection.execute(
                    "SELECT coalesce(sum(child_count),0) FROM virtual_product_segments "
                    "WHERE level<?",
                    (level,),
                ).fetchone()[0]
                if prior_virtual:
                    # Every virtual state would have to participate in the next
                    # exact frontier.  The current checkpoint preserves them via
                    # rank/unrank, but expanding that frontier exceeds the
                    # declared finite compute store; this is not grammar closure.
                    raise ComputeLimitReached("VIRTUAL_FRONTIER_COMPUTE_BUDGET")
                for operator in grammar.UNARY:
                    self._run_phase(level, f"unary:{operator.__name__}", operator.__name__)
                for operator in grammar.BINARY:
                    self._run_phase(level, f"binary:{operator.__name__}", operator.__name__)
                rows.append(self._complete_level(level))
            termination_class = "REQUESTED_LEVEL_COMPLETED"
            cause = "LEVEL_TARGET"
        except ComputeLimitReached as exc:
            self.connection.commit()
            self._set_meta("termination_class", "COMPUTATIONAL_TERMINATION")
            self._set_meta("termination_cause", exc.cause)
            self.connection.commit()
            termination_class = "COMPUTATIONAL_TERMINATION"
            cause = exc.cause
        return {
            "termination_class": termination_class,
            "cause": cause,
            "completed_level": int(self._meta("completed_level", "0")),
            "requested_level": requested_level,
            "peak_rss_mb": rss_mb(),
            "database": str(self.database),
            "levels_completed_this_run": rows,
        }

    def reconstruct_signature(self, state_id: int, cache: dict | None = None) -> tuple:
        if cache is None:
            cache = {}
        if state_id in cache:
            return cache[state_id]
        state = self._load_ref(state_id)
        parts = tuple(
            sorted(self.reconstruct_signature(part._state_id, cache) for part in state.parts)
        )
        signature = (*scalar_signature(state), parts)
        cache[state_id] = signature
        return signature

    def level_rows(self) -> list[dict[str, Any]]:
        columns = (
            "level,total_states,new_states,max_dim,derivations,"
            "logical_candidate_pairs,streamed_operator_candidates,"
            "duplicates_rejected,peak_rss_mb,wall_seconds,checkpoint_path"
        )
        names = columns.split(",")
        return [
            dict(zip(names, row))
            for row in self.connection.execute(
                f"SELECT {columns} FROM level_stats ORDER BY level"
            )
        ]

    def analysis(self) -> dict[str, Any]:
        completed = int(self._meta("completed_level", "0"))
        operator_rows = {}
        virtual_product_count = self.connection.execute(
            "SELECT coalesce(sum(child_count),0) FROM virtual_product_segments"
        ).fetchone()[0]
        for operator in grammar.UNARY + grammar.BINARY:
            name = operator.__name__
            attempted, successful, unique_states, duplicates = self.connection.execute(
                "SELECT coalesce(sum(attempted),0),coalesce(sum(successful),0),"
                "coalesce(sum(unique_states),0),coalesce(sum(duplicate_states),0) "
                "FROM phase_progress WHERE phase IN (?,?)",
                (f"unary:{name}", f"binary:{name}"),
            ).fetchone()
            edges, children, max_dim = self.connection.execute(
                "SELECT count(*),count(DISTINCT output),coalesce(max(s.dim),0) "
                "FROM derivations d JOIN states s ON s.id=d.output WHERE d.operator=?",
                (name,),
            ).fetchone()
            operator_rows[name] = {
                "scheduled_applications": attempted,
                "successful_applications": successful,
                "unique_children_first_inserted": unique_states,
                "duplicate_children": duplicates,
                "unique_derivation_classes": edges,
                "distinct_children": children,
                "maximum_child_dimension": max_dim,
            }
            if name == "op_product" and virtual_product_count:
                operator_rows[name]["unique_derivation_classes"] += virtual_product_count
                operator_rows[name]["distinct_children"] += virtual_product_count
                operator_rows[name]["maximum_child_dimension"] = max(
                    operator_rows[name]["maximum_child_dimension"],
                    self.connection.execute(
                        "SELECT max(maximum_child_dimension) FROM virtual_product_segments"
                    ).fetchone()[0],
                )

        confluences = self.connection.execute(
            "SELECT count(*) FROM (SELECT output FROM derivations "
            "GROUP BY output HAVING count(*)>1)"
        ).fetchone()[0]
        reciprocal_unary = self.connection.execute(
            "SELECT count(*) FROM derivations a JOIN derivations b "
            "ON a.input_b=0 AND b.input_b=0 AND a.input_a=b.output "
            "AND a.output=b.input_a AND a.id<b.id"
        ).fetchone()[0]
        quotient_states = self.connection.execute(
            "SELECT count(*) FROM (SELECT kind,dim,ord,sym,sq,anti,mult,bc,dual,occ "
            "FROM states GROUP BY kind,dim,ord,sym,sq,anti,mult,bc,dual,occ)"
        ).fetchone()[0]
        repeated_motifs = self.connection.execute(
            "SELECT count(*) FROM (SELECT 1 FROM states GROUP BY "
            "kind,dim,ord,sym,sq,anti,mult,bc,dual,occ HAVING count(*)>1)"
        ).fetchone()[0]
        distinct_kinds = self.connection.execute(
            "SELECT count(DISTINCT kind) FROM states"
        ).fetchone()[0]
        path_motifs = self.connection.execute(
            "SELECT count(*) FROM (SELECT d.operator,a.kind,b.kind,o.kind "
            "FROM derivations d JOIN states a ON a.id=d.input_a "
            "LEFT JOIN states b ON b.id=d.input_b JOIN states o ON o.id=d.output "
            "GROUP BY d.operator,a.kind,b.kind,o.kind)"
        ).fetchone()[0]
        return {
            "completed_level": completed,
            "termination_class": self._meta("termination_class"),
            "termination_cause": self._meta("termination_cause"),
            "levels": self.level_rows(),
            "operators": operator_rows,
            "confluent_states": confluences,
            "cycles": reciprocal_unary,
            "distinct_kinds": distinct_kinds,
            "material_quotient_structural_states": quotient_states,
            "material_repeated_structural_motifs": repeated_motifs,
            "quotient_note": (
                "USE_LONGITUDINAL_ANALYZER_FOR_VIRTUAL_SEGMENTS"
                if virtual_product_count
                else "MATERIAL_SET_IS_COMPLETE"
            ),
            "distinct_immediate_operator_path_motifs": path_motifs,
            "virtual_product_states": virtual_product_count,
            "virtual_product_representation": (
                "EXACT_RANKED_PARENT_PAIR_SEGMENTS" if virtual_product_count else "NONE"
            ),
        }


def open_engine(
    database: Path,
    limits: ComputeLimits,
    *,
    batch_size: int = 2_000,
    symbolic_product_threshold: int | None = None,
) -> StreamingExpansion:
    return StreamingExpansion(
        database,
        limits,
        batch_size=batch_size,
        symbolic_product_threshold=symbolic_product_threshold,
    )
