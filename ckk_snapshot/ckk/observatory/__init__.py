"""External functional-awareness observatory for KAIROS.

This package is intentionally separate from :mod:`ckk.sovereign`.  The
production organism emits a narrow stream of observable outcomes; it never
imports this package or reads the Observatory's storage.
"""

from .metrics import METRICS, PRIMARY_AXES
from .store import ObservatoryStore

__all__ = ["METRICS", "PRIMARY_AXES", "ObservatoryStore"]
