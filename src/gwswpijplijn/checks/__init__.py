"""Checks uit het checkregister die de GWSW-nulmeting niet dekt."""

from gwswpijplijn.checks import administratief as _administratief  # noqa: F401  (registry)
from gwswpijplijn.checks import attributen as _attributen  # noqa: F401  (vult de registry)
from gwswpijplijn.checks import betrouwbaarheid as _betrouwbaarheid  # noqa: F401  (registry)
from gwswpijplijn.checks import extern as _extern  # noqa: F401  (vult de registry)
from gwswpijplijn.checks import hoogten as _hoogten  # noqa: F401  (vult de registry)
from gwswpijplijn.checks import netwerk as _netwerk  # noqa: F401  (vult de registry)
from gwswpijplijn.checks import randvoorzieningen as _rvz  # noqa: F401  (vult de registry)
from gwswpijplijn.checks import topologie as _topologie  # noqa: F401  (vult de registry)
from gwswpijplijn.checks.base import (
    REGISTRY,
    Check,
    CheckContext,
    CheckOutcome,
    CheckRun,
    Dimension,
    Finding,
    Severity,
    SkeletonCheck,
    objecten_in_gebied,
    register,
    run_checks,
)

__all__ = [
    "REGISTRY",
    "Check",
    "CheckContext",
    "CheckOutcome",
    "CheckRun",
    "Dimension",
    "Finding",
    "Severity",
    "SkeletonCheck",
    "objecten_in_gebied",
    "register",
    "run_checks",
]
