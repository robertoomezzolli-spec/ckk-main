#!/usr/bin/env python3
"""External numeric-closure audit for the sealed CKK cascade.

Question: does the *naked numerical sequence* of 2*pi carry a closure/recurrence
signature that is exceptional relative to pi, e, phi, sqrt(2), Fibonacci, and a
pseudorandom null?

INTEGRITY FIREWALL
------------------
- This file is OUTSIDE the CKK kernel and does not import grammar.py or expand.py.
- It does not modify seeds, operators, generation, or scoring inside CKK.
- The test is about numerical sequences only. No physics labels or formula matches
  are used.
- The primary criterion is frozen below before looking at results.

Why multiple bases: a claim about the number itself should not depend on decimal
notation. We therefore repeat the same audit in bases 2, 3, 5, 7, 10 and 16.

Primary PASS criterion (predeclared):
  1) 2*pi must have the highest closure_score among {2pi, pi, e, phi, sqrt2,
     random} in at least 4 of 6 bases; AND
  2) its mean closure_score must exceed the strongest nonrandom mathematical
     control by at least 0.05; AND
  3) it must not be beaten by the structured Fibonacci-word positive control.

The threshold is intentionally hard. A generic irrational-looking digit stream is
not evidence of closure.
"""
from __future__ import annotations

from decimal import Decimal, getcontext
from hashlib import sha256
import json
import math
from pathlib import Path
from collections import Counter

N = 1536
BASES = (2, 3, 5, 7, 10, 16)
BLOCKS = (2, 3, 4, 5, 6)
WINDOW = 256
PREFIXES = (96, 192, 384, 768, 1536)
OUT = Path(__file__).resolve().parents[1] / "results" / "numeric_closure" / "audit.json"

# enough precision to emit N base-16 digits plus guard digits
getcontext().prec = 2600


def pi_chudnovsky() -> Decimal:
    # Chudnovsky with Decimal arithmetic; ~14 digits per term.
    C = Decimal(426880) * Decimal(10005).sqrt()
    M = 1
    L = 13591409
    X = 1
    K = 6
    S = Decimal(L)
    for i in range(1, 190):
        M = (M * (K**3 - 16*K)) // (i**3)
        L += 545140134
        X *= -262537412640768000
        S += Decimal(M * L) / Decimal(X)
        K += 12
    return C / S


def constants():
    pi = pi_chudnovsky()
    e = Decimal(1).exp()
    sqrt2 = Decimal(2).sqrt()
    phi = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
    return {
        "2pi": pi * 2,
        "pi": pi,
        "e": e,
        "phi": phi,
        "sqrt2": sqrt2,
    }


def base_digits(x: Decimal, base: int, n: int) -> list[int]:
    # fractional digits only; integer part is deliberately discarded so the
    # score cannot trivially distinguish pi from 2*pi by leading integer.
    y = x - int(x)
    out = []
    b = Decimal(base)
    for _ in range(n):
        y *= b
        d = int(y)
        out.append(d)
        y -= d
    return out


def prng_digits(base: int, n: int) -> list[int]:
    # Deterministic cryptographic null, fixed seed.
    out = []
    ctr = 0
    while len(out) < n:
        h = sha256(f"ckk-numeric-null-v1:{base}:{ctr}".encode()).digest()
        ctr += 1
        for byte in h:
            # rejection avoids modulo bias
            lim = 256 - (256 % base)
            if byte < lim:
                out.append(byte % base)
                if len(out) == n:
                    break
    return out


def fibonacci_word(n: int) -> list[int]:
    # canonical Fibonacci word: 0 -> 01, 1 -> 0
    s = [0]
    while len(s) < n:
        t = []
        for v in s:
            t.extend((0, 1) if v == 0 else (0,))
        s = t
    return s[:n]


def normalized_entropy(seq: list[int]) -> float:
    c = Counter(seq)
    if len(c) <= 1:
        return 0.0
    H = -sum((v/len(seq)) * math.log(v/len(seq)) for v in c.values())
    return H / math.log(len(c))


def exact_period_strength(seq: list[int]) -> float:
    """1-p/n for the shortest exact period p, else 0.

    Period here means s[i] == s[i-p] for all i>=p; it does not require n to be
    a multiple of p. This is a strict closure observable, not approximate fit.
    """
    n = len(seq)
    for p in range(1, n//2 + 1):
        if all(seq[i] == seq[i-p] for i in range(p, n)):
            return 1.0 - p/n
    return 0.0


def recurrence_excess(seq: list[int], k: int, window: int) -> float:
    """Observed near-return rate minus an iid baseline estimated from blocks."""
    n = len(seq) - k + 1
    blocks = [tuple(seq[i:i+k]) for i in range(n)]
    freq = Counter(blocks)
    # empirical iid-like collision baseline from block frequencies
    p_collision = sum((v/n)**2 for v in freq.values())
    hits = 0
    trials = 0
    for i in range(n):
        target = blocks[i]
        hi = min(n, i + 1 + window)
        if i + 1 < hi:
            trials += 1
            if target in blocks[i+1:hi]:
                hits += 1
    observed = hits / trials if trials else 0.0
    expected = 1.0 - (1.0 - p_collision) ** min(window, max(n-1, 0))
    return observed - expected


def lz_phrase_ratio(seq: list[int]) -> float:
    # Simple LZ78 phrase count normalized by n/log n. Larger ~= less compressible.
    dictionary = set()
    phrase = tuple()
    phrases = 0
    for x in seq:
        cand = phrase + (x,)
        if cand in dictionary:
            phrase = cand
        else:
            dictionary.add(cand)
            phrases += 1
            phrase = tuple()
    if phrase:
        phrases += 1
    n = len(seq)
    return phrases / (n / max(math.log2(n), 1.0))


def score(seq: list[int]) -> dict:
    period_scores = [exact_period_strength(seq[:m]) for m in PREFIXES]
    recur = [recurrence_excess(seq, k, WINDOW) for k in BLOCKS]
    # closure_score deliberately rewards exact closure strongly, then positive
    # recurrence excess, and mildly rewards compressibility. No physics input.
    entropy = normalized_entropy(seq)
    lz = lz_phrase_ratio(seq)
    closure = (
        0.60 * (sum(period_scores) / len(period_scores))
        + 0.30 * max(0.0, sum(recur) / len(recur))
        + 0.10 * max(0.0, 1.0 - min(lz, 1.0))
    )
    return {
        "closure_score": closure,
        "exact_period_strength_mean": sum(period_scores)/len(period_scores),
        "recurrence_excess_mean": sum(recur)/len(recur),
        "entropy_normalized": entropy,
        "lz_phrase_ratio": lz,
        "period_scores": period_scores,
        "recurrence_excess": dict(zip(map(str, BLOCKS), recur)),
    }


def main() -> int:
    vals = constants()
    results = {name: {} for name in [*vals.keys(), "random", "fibonacci_word"]}

    for base in BASES:
        for name, value in vals.items():
            results[name][str(base)] = score(base_digits(value, base, N))
        results["random"][str(base)] = score(prng_digits(base, N))
        # Fibonacci word is representation-independent; repeat same control per base
        results["fibonacci_word"][str(base)] = score(fibonacci_word(N))

    competitors = ("2pi", "pi", "e", "phi", "sqrt2", "random")
    winners = []
    for base in BASES:
        b = str(base)
        ranked = sorted(competitors, key=lambda n: results[n][b]["closure_score"], reverse=True)
        winners.append({"base": base, "winner": ranked[0], "ranking": ranked,
                        "scores": {n: results[n][b]["closure_score"] for n in competitors}})

    means = {name: sum(results[name][str(b)]["closure_score"] for b in BASES)/len(BASES)
             for name in results}
    wins_2pi = sum(w["winner"] == "2pi" for w in winners)
    strongest_math_control = max(("pi", "e", "phi", "sqrt2"), key=lambda n: means[n])
    margin = means["2pi"] - means[strongest_math_control]
    pass_primary = wins_2pi >= 4 and margin >= 0.05 and means["2pi"] >= means["fibonacci_word"]

    payload = {
        "schema": "ckk.numeric-closure-audit.v1",
        "status": "NUMERIC_CLOSURE_PASS" if pass_primary else "NUMERIC_CLOSURE_FAIL",
        "question": "Is the naked numerical sequence of 2*pi exceptionally closure-like relative to controls?",
        "firewall": "external-only; CKK kernel not imported or modified",
        "predeclared_primary": {
            "2pi_wins_required": 4,
            "bases": list(BASES),
            "mean_margin_over_strongest_math_control_required": 0.05,
            "must_not_lose_to_fibonacci_word": True,
        },
        "summary": {
            "2pi_base_wins": wins_2pi,
            "mean_scores": means,
            "strongest_math_control": strongest_math_control,
            "2pi_margin": margin,
        },
        "by_base": winners,
        "full_metrics": results,
        "interpretation_boundary": (
            "PASS would support only a representation-robust numerical closure anomaly. "
            "FAIL means the decimal/base expansion itself does not carry the special closure signal; "
            "it does not test or weaken the broader CKK cascade."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
