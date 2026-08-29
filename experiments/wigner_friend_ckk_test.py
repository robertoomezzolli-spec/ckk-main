#!/usr/bin/env python3
"""Executable Wigner-friend test for the CKK/TFF reversibility boundary.

No collapse postulate is assumed.  S measures into F by a CNOT.  A sequence of
fresh environment qubits stores a tunable record.  Their branch overlap is
gamma = product(cos(theta_j)); this is the exact coherence left for Wigner.
"""

from __future__ import annotations

import math
import unittest

import numpy as np


ZERO = np.array([1.0, 0.0], dtype=complex)
ONE = np.array([0.0, 1.0], dtype=complex)
PLUS_SF = (np.kron(ZERO, ZERO) + np.kron(ONE, ONE)) / math.sqrt(2)


def cnot(state: np.ndarray, control: int, target: int, qubits: int) -> np.ndarray:
    out = np.zeros_like(state)
    for basis, amp in enumerate(state):
        bits = [(basis >> (qubits - 1 - q)) & 1 for q in range(qubits)]
        if bits[control]:
            bits[target] ^= 1
        mapped = 0
        for bit in bits:
            mapped = (mapped << 1) | bit
        out[mapped] += amp
    return out


def controlled_ry(
    state: np.ndarray, control: int, target: int, theta: float, qubits: int
) -> np.ndarray:
    """Apply |0><0| x I + |1><1| x Ry(2 theta)."""
    out = state.copy()
    c = math.cos(theta)
    s = math.sin(theta)
    for basis in range(2**qubits):
        bits = [(basis >> (qubits - 1 - q)) & 1 for q in range(qubits)]
        if not bits[control] or bits[target]:
            continue
        partner = basis | (1 << (qubits - 1 - target))
        a, b = state[basis], state[partner]
        out[basis] = c * a - s * b
        out[partner] = s * a + c * b
    return out


def reduced_density(state: np.ndarray, keep: tuple[int, ...], qubits: int) -> np.ndarray:
    tensor = state.reshape((2,) * qubits)
    trace = tuple(q for q in range(qubits) if q not in keep)
    perm = keep + trace
    matrix = np.transpose(tensor, perm).reshape(2 ** len(keep), -1)
    return matrix @ matrix.conj().T


def experiment(theta: float, records: int, phase: float = 0.0) -> dict[str, float]:
    qubits = 2 + records
    s = (ZERO + np.exp(-1j * phase) * ONE) / math.sqrt(2)
    state = np.kron(np.kron(s, ZERO), np.tile([1.0], 1))
    for _ in range(records):
        state = np.kron(state, ZERO)

    state = cnot(state, 0, 1, qubits)
    for env in range(records):
        state = controlled_ry(state, 1, 2 + env, theta, qubits)

    rho_sf = reduced_density(state, (0, 1), qubits)
    rho_f = reduced_density(state, (1,), qubits)
    p_wigner_plus = float(np.real(PLUS_SF.conj() @ rho_sf @ PLUS_SF))
    gamma = math.cos(theta) ** records

    # Undoing only S-F correlation leaves environment records untouched.
    sf_only_reversed = cnot(state, 0, 1, qubits)
    rho_s_after_partial = reduced_density(sf_only_reversed, (0,), qubits)

    # Undo all record writes, then undo S-F measurement.
    fully_reversed = state
    for env in reversed(range(records)):
        fully_reversed = controlled_ry(fully_reversed, 1, 2 + env, -theta, qubits)
    fully_reversed = cnot(fully_reversed, 0, 1, qubits)
    rho_s_after_full = reduced_density(fully_reversed, (0,), qubits)
    target_s = np.outer(s, s.conj())

    return {
        "gamma": gamma,
        "wigner_plus": p_wigner_plus,
        "analytic_plus": 0.5 * (1.0 + gamma * math.cos(phase)),
        "friend_p0": float(np.real(rho_f[0, 0])),
        "friend_p1": float(np.real(rho_f[1, 1])),
        "friend_coherence": float(abs(rho_f[0, 1])),
        "partial_s_coherence": float(abs(rho_s_after_partial[0, 1])),
        "full_reversal_error": float(np.max(abs(rho_s_after_full - target_s))),
    }


def wigner_fringe(
    time: float, omega_s: float, omega_f: float, gamma: float, interaction_shift: float = 0.0
) -> float:
    """Bell-plus probability for E_11-E_00 = hbar*(omega_s+omega_f+shift)."""
    omega_relative = omega_s + omega_f + interaction_shift
    return 0.5 * (1.0 + gamma * math.cos(omega_relative * time))


class WignerFriendBoundaryTests(unittest.TestCase):
    def test_unitary_friend_record_is_locally_diagonal_globally_coherent(self):
        r = experiment(theta=0.0, records=1)
        self.assertAlmostEqual(r["friend_coherence"], 0.0, places=12)
        self.assertAlmostEqual(r["wigner_plus"], 1.0, places=12)

    def test_record_overlap_exactly_controls_wigner_visibility(self):
        for theta in (0.0, 0.2, 0.7, math.pi / 2):
            for records in (1, 2, 4):
                r = experiment(theta=theta, records=records, phase=0.37)
                self.assertAlmostEqual(r["wigner_plus"], r["analytic_plus"], places=12)

    def test_absorbing_orthogonal_record_kills_interference(self):
        r = experiment(theta=math.pi / 2, records=1)
        self.assertAlmostEqual(r["gamma"], 0.0, places=12)
        self.assertAlmostEqual(r["wigner_plus"], 0.5, places=12)
        self.assertAlmostEqual(r["partial_s_coherence"], 0.0, places=12)

    def test_partial_uncompute_cannot_erase_external_record(self):
        r = experiment(theta=0.7, records=3)
        self.assertAlmostEqual(r["partial_s_coherence"], 0.5 * r["gamma"], places=12)

    def test_full_uncompute_restores_coherence_and_erases_friend_record(self):
        r = experiment(theta=1.1, records=4, phase=0.63)
        self.assertLess(r["full_reversal_error"], 1e-12)

    def test_sum_frequency_requires_additive_branch_energy(self):
        omega_s, omega_f, time, gamma = 1.7, 2.3, 0.41, 0.72
        additive = wigner_fringe(time, omega_s, omega_f, gamma)
        expected = 0.5 * (1.0 + gamma * math.cos((omega_s + omega_f) * time))
        self.assertAlmostEqual(additive, expected, places=12)

        shifted = wigner_fringe(time, omega_s, omega_f, gamma, interaction_shift=0.9)
        self.assertNotAlmostEqual(shifted, expected, places=6)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WignerFriendBoundaryTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("\nNUMERICAL SWEEP")
    print("records  theta      gamma       P(W+)      friend coherence")
    for records in (1, 2, 4, 8):
        for theta in (0.0, 0.35, 0.75, math.pi / 2):
            row = experiment(theta, records)
            print(
                f"{records:7d}  {theta:5.2f}  {row['gamma']:10.6f}  "
                f"{row['wigner_plus']:10.6f}  {row['friend_coherence']:16.6f}"
            )
    raise SystemExit(not result.wasSuccessful())
