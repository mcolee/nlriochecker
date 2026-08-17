"""Checks uit het checkregister die de GWSW-nulmeting niet dekt."""

from nlriochecker.checks import administratief as _administratief  # noqa: F401  (registry)
from nlriochecker.checks import attributen as _attributen  # noqa: F401  (vult de registry)
from nlriochecker.checks import betrouwbaarheid as _betrouwbaarheid  # noqa: F401  (registry)
from nlriochecker.checks import extern as _extern  # noqa: F401  (vult de registry)
from nlriochecker.checks import hoogten as _hoogten  # noqa: F401  (vult de registry)
from nlriochecker.checks import netwerk as _netwerk  # noqa: F401  (vult de registry)
from nlriochecker.checks import randvoorzieningen as _rvz  # noqa: F401  (vult de registry)
from nlriochecker.checks import topologie as _topologie  # noqa: F401  (vult de registry)
from nlriochecker.checks.base import (
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
