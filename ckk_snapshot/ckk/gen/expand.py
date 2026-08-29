"""Expansion core.

`expand()` preserves the historical two-return-value API used by the snapshot.
For scientific/audit work use `expand_auditable()` or
`expand_structural_auditable()`: they record every operator application as a
derivation event, including alternative derivations whose output structure
already exists. Binary inputs are one event, not two false "confluences".
"""
from dataclasses import dataclass
from typing import Tuple

from grammar import SEEDS, UNARY, BINARY


COMMUTATIVE_OPERATORS = frozenset({"op_product"})


@dataclass(frozen=True)
class Derivation:
    operator: str
    inputs: Tuple
    output: tuple
    level: int

    def event_key(self):
        """Canonical identity of one operator application.

        Commutative operators normalize input order so product(a,b) and
        product(b,a) cannot masquerade as independent derivations.
        """
        inputs = self.inputs
        if self.operator in COMMUTATIVE_OPERATORS:
            inputs = tuple(sorted(inputs))
        return self.operator, inputs, self.output


def _expand_core(levels=4, cap=400, structural_identity=False):
    identity = (lambda s: s.structural_sig()) if structural_identity else (lambda s: s.sig())
    pool = {identity(s): s for s in SEEDS}
    legacy_edges = []
    derivations = []

    for lvl in range(levels):
        new = {}
        items = list(pool.values())

        for s in items:
            for op in UNARY:
                r = op(s)
                if not r:
                    continue
                source_id = identity(s)
                target_id = identity(r)
                # An idempotent operation is not a graph transition and must
                # not manufacture a derivation event or self-loop.
                if target_id == source_id:
                    continue
                derivations.append(Derivation(op.__name__, (source_id,), target_id, lvl + 1))
                if target_id not in pool and target_id not in new:
                    new[target_id] = r
                    if not structural_identity:
                        # Historical edge representation retained only for the
                        # sealed compatibility path.
                        legacy_edges.append((s.sig(), r.sig(), op.__name__))

        for a in items:
            for b in items:
                for op in BINARY:
                    r = op(a, b)
                    if not r:
                        continue

                    input_ids = (identity(a), identity(b))
                    target_id = identity(r)
                    if target_id in input_ids:
                        continue
                    # One binary operator application is ONE derivation event with
                    # two inputs. This prevents input arity from masquerading as
                    # independent derivational confluence.
                    derivations.append(Derivation(op.__name__, input_ids, target_id, lvl + 1))
                    if target_id not in pool and target_id not in new:
                        new[target_id] = r
                        if not structural_identity:
                            # Keep old edge projection exactly for legacy consumers.
                            legacy_edges.append((a.sig(), r.sig(), op.__name__))
                            legacy_edges.append((b.sig(), r.sig(), op.__name__))

        pool.update(new)
        if len(pool) > cap:
            break

    return pool, legacy_edges, derivations


def expand(levels=4, cap=400):
    """Historical API. Do not use edge indegree as derivational confluence."""
    pool, edges, _ = _expand_core(levels=levels, cap=cap, structural_identity=False)
    return pool, edges


def expand_auditable(levels=4, cap=400):
    """Historical node identity plus complete derivation-event provenance."""
    pool, _, derivations = _expand_core(levels=levels, cap=cap, structural_identity=False)
    return pool, derivations


def expand_structural_auditable(levels=4, cap=400):
    """Scientific expansion using provenance-free structural node identity.

    This is intentionally separate from `expand()` so sealed historical
    snapshots stay reproducible. It is the candidate path for future fresh
    generations after cross-domain regression review.
    """
    pool, _, derivations = _expand_core(levels=levels, cap=cap, structural_identity=True)
    return pool, derivations


def derivational_confluences(derivations):
    """Outputs produced by >=2 distinct derivation events.

    Duplicate re-evaluation of the same event and commutative input reversal do
    not inflate the count.
    """
    by_output = {}
    for d in derivations:
        by_output.setdefault(d.output, set()).add(d.event_key())
    return {out: events for out, events in by_output.items() if len(events) >= 2}


if __name__ == '__main__':
    p, e = expand()
    _, d = expand_auditable()
    sp, sd = expand_structural_auditable()
    c = derivational_confluences(sd)
    print(f"Historical structures: {len(p)}")
    print(f"Legacy edges: {len(e)}")
    print(f"Historical derivation events: {len(d)}")
    print(f"Structural states: {len(sp)}")
    print(f"Structural derivational confluences: {len(c)}")
