"""PuLP implementation of the ShiftWise volunteer assignment model.

The model and ``solve(volunteers, slots) -> SolverResult`` interface follow
PROJECT_BRIEF.md. Only eligible volunteer/slot pairs become binary variables;
availability and required skills are therefore hard constraints. Coverage is
maximised first, with preference matches breaking ties between equally covered
rosters. Slots may remain uncovered.

This module assumes Manas will generate the required shared work per
IMPLEMENTATION_PLAN.md (``shiftwise.models`` types/``SolverResult``,
``shiftwise.helpers`` eligibility and overlap helpers, and
``shiftwise.validation``/metrics as applicable). When those modules exist this
solver prefers them; temporary local fallbacks keep the solver usable before
integration. Fallback/helper API names assumed here (until Manas's API note):
``models.SolverResult`` (and optional ``Volunteer``/``ShiftSlot`` types),
``helpers.is_eligible(volunteer, slot) -> bool`` and
``helpers.slots_overlap(slot_a, slot_b) -> bool`` (or ``overlaps``).

Backend selection prefers CBC from older PuLP releases, then the native HiGHS
API used by PuLP 4.x (which needs ``highspy`` and ``numpy``), then any other
solver PuLP reports as available. See ``_make_solver`` for the exact sequence.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations
from typing import Any

import pulp

try:  # Manas-owned shared contract/types.
    from .models import SolverResult  # type: ignore[attr-defined]
except ImportError:  # Temporary fallback until Manas generates shiftwise.models.
    @dataclass(frozen=True)
    class SolverResult:
        """Result contract from PROJECT_BRIEF.md (local fallback)."""

        status: str  # "optimal", "feasible", or "no_solution"
        assignments: list[tuple[str, str]]
        filled_slots: int
        total_slots: int
        preference_count: int
        elapsed_seconds: float

# Optional shared model types (Manas-owned); solver logic uses documented fields.
try:
    from .models import ShiftSlot as _SharedShiftSlot  # type: ignore[attr-defined]
    from .models import Volunteer as _SharedVolunteer  # type: ignore[attr-defined]
except ImportError:
    _SharedVolunteer = None
    _SharedShiftSlot = None

# Manas-owned helpers (eligibility/overlap). Fall back to contract semantics.
try:
    from .helpers import is_eligible as _shared_is_eligible  # type: ignore[attr-defined]
except ImportError:
    _shared_is_eligible = None

_shared_slots_overlap = None
try:
    from .helpers import slots_overlap as _shared_slots_overlap  # type: ignore[attr-defined]
except ImportError:
    try:
        from .helpers import overlaps as _shared_slots_overlap  # type: ignore[attr-defined]
    except ImportError:
        _shared_slots_overlap = None


__all__ = ["SolverResult", "solve"]

_TIME_LIMIT_SECONDS = 30.0


@dataclass(frozen=True)
class _Volunteer:
    id: str
    skills: frozenset[str]
    available_slot_ids: frozenset[str]
    max_assignments: int
    preferred_slot_ids: frozenset[str]


@dataclass(frozen=True)
class _Slot:
    id: str
    role: str
    start_time: int
    end_time: int
    required_skill: str | None


def _require(record: Any, field: str, owner: str) -> Any:
    try:
        return getattr(record, field)
    except AttributeError as error:
        raise ValueError(f"{owner} is missing required field {field!r}.") from error


def _string_set(values: Any, field: str, owner: str) -> frozenset[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise ValueError(f"{owner}.{field} must be a collection of strings.")
    items = set(values)
    if any(not isinstance(item, str) for item in items):
        raise ValueError(f"{owner}.{field} must contain only strings.")
    return frozenset(items)


def _normalise_volunteers(volunteers: Iterable[Any]) -> list[_Volunteer]:
    result: list[_Volunteer] = []
    seen: set[str] = set()
    for index, record in enumerate(volunteers):
        owner = f"volunteer[{index}]"
        volunteer_id = _require(record, "id", owner)
        if not isinstance(volunteer_id, str) or not volunteer_id:
            raise ValueError(f"{owner}.id must be a nonempty string.")
        if volunteer_id in seen:
            raise ValueError(f"Duplicate volunteer ID {volunteer_id!r}.")
        seen.add(volunteer_id)

        cap = _require(record, "max_assignments", owner)
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
            raise ValueError(f"{owner}.max_assignments must be a nonnegative integer.")

        result.append(
            _Volunteer(
                id=volunteer_id,
                skills=_string_set(_require(record, "skills", owner), "skills", owner),
                available_slot_ids=_string_set(
                    _require(record, "available_slot_ids", owner),
                    "available_slot_ids",
                    owner,
                ),
                max_assignments=cap,
                preferred_slot_ids=_string_set(
                    _require(record, "preferred_slot_ids", owner),
                    "preferred_slot_ids",
                    owner,
                ),
            )
        )
    return result


def _normalise_slots(slots: Iterable[Any]) -> list[_Slot]:
    result: list[_Slot] = []
    seen: set[str] = set()
    for index, record in enumerate(slots):
        owner = f"slot[{index}]"
        slot_id = _require(record, "id", owner)
        if not isinstance(slot_id, str) or not slot_id:
            raise ValueError(f"{owner}.id must be a nonempty string.")
        if slot_id in seen:
            raise ValueError(f"Duplicate slot ID {slot_id!r}.")
        seen.add(slot_id)

        start = _require(record, "start_time", owner)
        end = _require(record, "end_time", owner)
        if (
            isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or end <= start
        ):
            raise ValueError(f"{owner} needs integer times with end_time > start_time.")

        role = _require(record, "role", owner)
        if not isinstance(role, str):
            raise ValueError(f"{owner}.role must be a string.")

        required_skill = _require(record, "required_skill", owner)
        if required_skill is not None and not isinstance(required_skill, str):
            raise ValueError(f"{owner}.required_skill must be a string or None.")

        result.append(
            _Slot(
                id=slot_id,
                role=role,
                start_time=start,
                end_time=end,
                required_skill=required_skill,
            )
        )
    return result


def _is_eligible(volunteer: Any, slot: Any) -> bool:
    """Eligibility uses availability plus any required skill.

    Prefers Manas's ``helpers.is_eligible`` when available; falls back to the
    contract semantics so this module remains usable before integration.
    """
    if _shared_is_eligible is not None:
        return bool(_shared_is_eligible(volunteer, slot))
    if slot.id not in volunteer.available_slot_ids:
        return False
    if slot.required_skill is not None and slot.required_skill not in volunteer.skills:
        return False
    return True


def _overlaps(first: Any, second: Any) -> bool:
    """Half-open interval overlap: ``start1 < end2 and start2 < end1``.

    Prefers Manas's ``helpers.slots_overlap``/``overlaps`` when available.
    """
    if _shared_slots_overlap is not None:
        return bool(_shared_slots_overlap(first, second))
    return first.start_time < second.end_time and second.start_time < first.end_time


def _candidate_solvers() -> list[tuple[str, Any]]:
    """Return solver factories in preference order, without requiring all to exist."""
    candidates: list[tuple[str, Any]] = []

    classic_cbc = getattr(pulp, "PULP_CBC_CMD", None)  # PuLP 2.x/3.x bundled CBC
    if classic_cbc is not None:
        candidates.append(("CBC (PULP_CBC_CMD)", classic_cbc))

    native_highs = getattr(pulp, "HiGHS", None)  # PuLP 4.x native HiGHS API
    if native_highs is None:
        try:
            from pulp.apis import HiGHS as native_highs
        except (ImportError, AttributeError):
            native_highs = None
    if native_highs is not None:
        candidates.append(("HiGHS", native_highs))

    for name in ("COIN_CMD", "HiGHS_CMD", "GLPK_CMD"):
        factory = getattr(pulp, name, None)
        if factory is not None:
            candidates.append((name, factory))
    return candidates


def _make_solver() -> Any:
    """Find a backend that can actually solve, not merely import."""
    problems: list[str] = []
    for name, factory in _candidate_solvers():
        try:
            try:
                solver = factory(msg=False, timeLimit=_TIME_LIMIT_SECONDS)
            except TypeError:
                solver = factory(msg=False)
            if solver.available():
                return solver
            problems.append(f"{name}: not available")
        except Exception as error:  # a broken backend should not hide the next candidate
            problems.append(f"{name}: {type(error).__name__}: {error}")

    raise RuntimeError(
        "No callable PuLP optimization backend was found. "
        "For PuLP 4.x install native HiGHS with `python -m pip install highspy numpy` "
        "or put a CBC/HiGHS executable on PATH; for older PuLP reinstall a release "
        "with its CBC backend. Detection: " + "; ".join(problems)
    )


def _new_binary(problem: Any, name: str) -> Any:
    """Create a binary variable with both classic PuLP and PuLP 4.x APIs."""
    if hasattr(problem, "add_variable"):
        return problem.add_variable(name, cat="Binary")
    return pulp.LpVariable(name, cat="Binary")


def _using_shared_contract() -> bool:
    return _SharedVolunteer is not None and _SharedShiftSlot is not None


def _variable_value(variable: Any) -> float | None:
    value = getattr(variable, "varValue", None)
    if value is None and hasattr(variable, "value"):
        value = variable.value()
    return value


def _status_text(raw_status: Any) -> str:
    if isinstance(raw_status, str):
        text = raw_status
    elif hasattr(raw_status, "name"):
        text = str(raw_status.name)
    else:
        try:
            text = pulp.LpStatus[raw_status] if hasattr(pulp, "LpStatus") else str(raw_status)
        except (KeyError, TypeError):
            text = str(raw_status)
    return re.sub(r"[^a-z]", "", text.lower())


def _normalize_status(raw_status: Any, has_incumbent: bool) -> str:
    text = _status_text(raw_status)
    if "optimal" in text:
        return "optimal"
    if "infeasible" in text or "unbounded" in text or "numericalerror" in text:
        return "no_solution"
    # Time/node/gap limits and interrupted/stopped/undefined runs can still have
    # a usable incumbent, which must be returned as a feasible result.
    if has_incumbent:
        return "feasible"
    return "no_solution"


def solve(volunteers: Iterable[Any], slots: Iterable[Any]) -> SolverResult:
    """Solve the ShiftWise assignment model with PuLP.

    Assumes validated/shared records per Manas's work: ``Volunteer``/``ShiftSlot``
    types and ``SolverResult`` in ``shiftwise.models``, with eligibility/overlap
    helpers in ``shiftwise.helpers``. Until those modules exist, local fallbacks
    normalise the documented fields and apply the contract semantics.

    Args:
        volunteers: Records with ``id``, ``name``, ``skills``,
            ``available_slot_ids``, ``max_assignments``, and
            ``preferred_slot_ids``. Collections may be sets or lists.
        slots: Records with ``id``, ``role``, ``start_time``, ``end_time``, and
            ``required_skill``; times are integer minutes after midnight.

    Returns:
        A ``SolverResult`` with normalized status and the incumbent roster.

    Raises:
        ValueError: Malformed records that should be caught by validation.
        RuntimeError: No callable PuLP backend could be found.
    """
    volunteer_records = list(volunteers) if _using_shared_contract() else _normalise_volunteers(volunteers)
    slot_records = list(slots) if _using_shared_contract() else _normalise_slots(slots)
    total_slots = len(slot_records)

    problem = pulp.LpProblem("ShiftWise_PuLP", pulp.LpMaximize)
    variables: dict[tuple[int, int], Any] = {}
    for volunteer_index, volunteer in enumerate(volunteer_records):
        for slot_index, slot in enumerate(slot_records):
            if _is_eligible(volunteer, slot):
                # Index-based names avoid illegal characters and ID collisions.
                variables[(volunteer_index, slot_index)] = _new_binary(
                    problem, f"x_{volunteer_index}_{slot_index}"
                )

    if not variables:
        # The zero assignment is the unique optimal (and feasible) roster.
        return SolverResult("optimal", [], 0, total_slots, 0, 0.0)

    by_slot: dict[int, list[Any]] = {index: [] for index in range(total_slots)}
    by_volunteer: dict[int, list[Any]] = {index: [] for index in range(len(volunteer_records))}
    for (volunteer_index, slot_index), variable in variables.items():
        by_slot[slot_index].append(variable)
        by_volunteer[volunteer_index].append(variable)

    for slot_index, terms in by_slot.items():
        problem += pulp.lpSum(terms) <= 1, f"slot_{slot_index}"

    for volunteer_index, terms in by_volunteer.items():
        cap = volunteer_records[volunteer_index].max_assignments
        problem += pulp.lpSum(terms) <= cap, f"cap_{volunteer_index}"

    for volunteer_index, volunteer in enumerate(volunteer_records):
        eligible_slot_indices = [
            slot_index
            for (other_index, slot_index) in variables
            if other_index == volunteer_index
        ]
        for first_index, second_index in combinations(eligible_slot_indices, 2):
            if _overlaps(slot_records[first_index], slot_records[second_index]):
                problem += (
                    variables[(volunteer_index, first_index)]
                    + variables[(volunteer_index, second_index)]
                    <= 1
                ), f"overlap_{volunteer_index}_{first_index}_{second_index}"

    coverage = pulp.lpSum(variables.values())
    preference = pulp.lpSum(
        variable
        for (volunteer_index, slot_index), variable in variables.items()
        if slot_records[slot_index].id in volunteer_records[volunteer_index].preferred_slot_ids
    )
    problem += (total_slots + 1) * coverage + preference

    solver = _make_solver()
    started = time.perf_counter()
    stats = problem.solve(solver)
    elapsed_seconds = time.perf_counter() - started

    raw_status = getattr(stats, "status", None) if stats is not None else None
    if raw_status is None:
        raw_status = getattr(problem, "status", "Undefined")

    assignments: list[tuple[str, str]] = []
    preference_count = 0
    for (volunteer_index, slot_index), variable in variables.items():
        value = _variable_value(variable)
        if value is None or value < 0.5:
            continue
        volunteer_id = volunteer_records[volunteer_index].id
        slot_id = slot_records[slot_index].id
        assignments.append((volunteer_id, slot_id))
        if slot_id in volunteer_records[volunteer_index].preferred_slot_ids:
            preference_count += 1

    assignments.sort(key=lambda pair: (pair[1], pair[0]))
    status = _normalize_status(raw_status, bool(assignments))
    return SolverResult(
        status=status,
        assignments=assignments,
        filled_slots=len({slot_id for _volunteer_id, slot_id in assignments}),
        total_slots=total_slots,
        preference_count=preference_count,
        elapsed_seconds=elapsed_seconds,
    )
