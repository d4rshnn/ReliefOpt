"""PuLP implementation of the shared ShiftWise assignment model."""

from __future__ import annotations

import re
import time
from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

import pulp

from .helpers import is_eligible, slots_overlap
from .models import SolverResult
from .validation import validate_inputs

_TIME_LIMIT_SECONDS = 30.0


def _field(record: Any, name: str) -> Any:
    return record[name] if isinstance(record, Mapping) else getattr(record, name)


def _candidate_solvers() -> list[tuple[str, Any]]:
    """List supported backends present in the installed PuLP release."""
    candidates: list[tuple[str, Any]] = []
    # Prefer the separately declared HiGHS backend; PuLP 3.3 marks its
    # bundled PULP_CBC_CMD interface as deprecated for the upcoming PuLP 4.
    for name in ("HiGHS", "COIN_CMD", "HiGHS_CMD", "GLPK_CMD", "PULP_CBC_CMD"):
        factory = getattr(pulp, name, None)
        if factory is None:
            continue
        if not callable(factory) and hasattr(factory, "available"):
            candidates.append((name, lambda candidate=factory, **_kwargs: candidate))
        else:
            candidates.append((name, factory))
    return candidates


def _make_solver() -> tuple[str, Any]:
    failures: list[str] = []
    for name, factory in _candidate_solvers():
        try:
            try:
                solver = factory(msg=False, timeLimit=_TIME_LIMIT_SECONDS)
            except TypeError:
                solver = factory(msg=False)
            if solver.available():
                return name, solver
            failures.append(f"{name}: backend not available")
        except Exception as error:
            failures.append(f"{name}: {type(error).__name__}: {error}")

    details = "; ".join(failures) or "PuLP exposed no supported solver interfaces."
    raise RuntimeError(
        "No callable PuLP optimization backend is available. Install the project's "
        "configured backend (HiGHS via highspy) or make CBC available. " + details
    )


def _new_binary(problem: Any, name: str) -> Any:
    """Create a binary variable across supported PuLP APIs."""
    if hasattr(problem, "add_variable"):
        return problem.add_variable(name, cat="Binary")
    return pulp.LpVariable(name, cat="Binary")


def _has_incumbent(variables: Mapping[tuple[int, int], Any]) -> bool:
    return any(
        (getattr(variable, "varValue", None) is not None)
        or (hasattr(variable, "value") and variable.value() is not None)
        for variable in variables.values()
    )


def _normalize_status(raw_status: Any, has_incumbent: bool) -> str:
    if isinstance(raw_status, str):
        status_text = raw_status.lower()
    elif hasattr(pulp, "LpStatus"):
        status_text = str(pulp.LpStatus.get(raw_status, raw_status)).lower()
    else:
        status_text = str(raw_status).lower()
    normalized = re.sub(r"[^a-z]", "", status_text)
    if "optimal" in normalized:
        return "optimal"
    if any(word in normalized for word in ("infeasible", "unbounded", "error")):
        return "no_solution"
    return "feasible" if has_incumbent else "no_solution"


def solve(volunteers: Iterable[Any], slots: Iterable[Any]) -> SolverResult:
    """Solve the same coverage-first model as the OR-Tools implementation.

    Records may be the shared dataclasses or mappings accepted by validation.
    A missing/unusable backend raises a descriptive ``RuntimeError``; it is
    never reported as a successful empty roster.
    """
    volunteer_records = list(volunteers)
    slot_records = list(slots)
    validate_inputs(volunteer_records, slot_records)
    total_slots = len(slot_records)

    problem = pulp.LpProblem("ShiftWise_PuLP", pulp.LpMaximize)
    variables: dict[tuple[int, int], Any] = {}
    for volunteer_index, volunteer in enumerate(volunteer_records):
        for slot_index, slot in enumerate(slot_records):
            if is_eligible(volunteer, slot):
                variables[(volunteer_index, slot_index)] = _new_binary(
                    problem, f"x_v{volunteer_index}_s{slot_index}"
                )

    if not variables:
        return SolverResult("optimal", [], 0, total_slots, 0, 0.0)

    by_slot = {index: [] for index in range(total_slots)}
    by_volunteer = {index: [] for index in range(len(volunteer_records))}
    for (volunteer_index, slot_index), variable in variables.items():
        by_slot[slot_index].append(variable)
        by_volunteer[volunteer_index].append(variable)

    for slot_index, terms in by_slot.items():
        problem += pulp.lpSum(terms) <= 1, f"slot_{slot_index}"

    for volunteer_index, terms in by_volunteer.items():
        cap = _field(volunteer_records[volunteer_index], "max_assignments")
        problem += pulp.lpSum(terms) <= cap, f"cap_{volunteer_index}"

    for volunteer_index in range(len(volunteer_records)):
        eligible_slot_indices = [
            slot_index for v_index, slot_index in variables if v_index == volunteer_index
        ]
        for first_index, second_index in combinations(eligible_slot_indices, 2):
            if slots_overlap(slot_records[first_index], slot_records[second_index]):
                problem += (
                    variables[(volunteer_index, first_index)]
                    + variables[(volunteer_index, second_index)]
                    <= 1
                ), f"overlap_v{volunteer_index}_s{first_index}_s{second_index}"

    coverage = pulp.lpSum(variables.values())
    preference = pulp.lpSum(
        variable
        for (volunteer_index, slot_index), variable in variables.items()
        if _field(slot_records[slot_index], "id")
        in _field(volunteer_records[volunteer_index], "preferred_slot_ids")
    )
    problem += (total_slots + 1) * coverage + preference

    backend_name, solver = _make_solver()
    started = time.perf_counter()
    try:
        problem.solve(solver)
    except Exception as error:
        raise RuntimeError(f"PuLP backend {backend_name} failed while solving: {error}") from error
    elapsed_seconds = time.perf_counter() - started

    status = _normalize_status(problem.status, _has_incumbent(variables))
    assignments: list[tuple[str, str]] = []
    preference_count = 0
    for (volunteer_index, slot_index), variable in variables.items():
        value = getattr(variable, "varValue", None)
        if value is None and hasattr(variable, "value"):
            value = variable.value()
        if value is None or value < 0.5:
            continue
        volunteer_id = _field(volunteer_records[volunteer_index], "id")
        slot_id = _field(slot_records[slot_index], "id")
        assignments.append((volunteer_id, slot_id))
        if slot_id in _field(volunteer_records[volunteer_index], "preferred_slot_ids"):
            preference_count += 1

    assignments.sort(key=lambda pair: (pair[1], pair[0]))
    return SolverResult(
        status=status,
        assignments=assignments,
        filled_slots=len(assignments),
        total_slots=total_slots,
        preference_count=preference_count,
        elapsed_seconds=elapsed_seconds,
    )
