"""OR-Tools CP-SAT implementation of the shared ShiftWise model."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from typing import Any

from ortools.sat.python import cp_model

from .helpers import is_eligible, slots_overlap
from .models import SolverResult
from .validation import validate_inputs


def _field(record: Any, name: str) -> Any:
    return record[name] if isinstance(record, Mapping) else getattr(record, name)


def solve(volunteers: Iterable[Any], slots: Iterable[Any]) -> SolverResult:
    """Return the coverage-first optimal or best feasible roster.

    Variables are created only for pairs that pass shared availability and
    skill eligibility. Input records are checked against the shared contract
    before model construction.
    """
    volunteer_list = list(volunteers)
    slot_list = list(slots)
    validate_inputs(volunteer_list, slot_list)

    total_slots = len(slot_list)
    if total_slots == 0:
        return SolverResult("optimal", [], 0, 0, 0, 0.0)

    model = cp_model.CpModel()
    volunteers_by_id = {_field(volunteer, "id"): volunteer for volunteer in volunteer_list}
    slots_by_id = {_field(slot, "id"): slot for slot in slot_list}

    variables: dict[tuple[str, str], cp_model.IntVar] = {}
    eligible_by_volunteer: dict[str, list[str]] = {volunteer_id: [] for volunteer_id in volunteers_by_id}
    eligible_by_slot: dict[str, list[str]] = {slot_id: [] for slot_id in slots_by_id}
    preferred_pairs: set[tuple[str, str]] = set()

    for volunteer_index, (volunteer_id, volunteer) in enumerate(volunteers_by_id.items()):
        preferences = set(_field(volunteer, "preferred_slot_ids"))
        for slot_index, (slot_id, slot) in enumerate(slots_by_id.items()):
            if not is_eligible(volunteer, slot):
                continue
            variables[(volunteer_id, slot_id)] = model.NewBoolVar(
                f"assign_v{volunteer_index}_s{slot_index}"
            )
            eligible_by_volunteer[volunteer_id].append(slot_id)
            eligible_by_slot[slot_id].append(volunteer_id)
            if slot_id in preferences:
                preferred_pairs.add((volunteer_id, slot_id))

    # If there are no eligible edges, the all-zero assignment is optimal and
    # no backend search is needed.
    if not variables:
        return SolverResult("optimal", [], 0, total_slots, 0, 0.0)

    for slot_id, volunteer_ids in eligible_by_slot.items():
        model.AddAtMostOne(variables[(volunteer_id, slot_id)] for volunteer_id in volunteer_ids)

    for volunteer_id, slot_ids in eligible_by_volunteer.items():
        cap = _field(volunteers_by_id[volunteer_id], "max_assignments")
        model.Add(sum(variables[(volunteer_id, slot_id)] for slot_id in slot_ids) <= cap)
        for index, first_id in enumerate(slot_ids):
            for second_id in slot_ids[index + 1:]:
                if slots_overlap(slots_by_id[first_id], slots_by_id[second_id]):
                    model.Add(
                        variables[(volunteer_id, first_id)]
                        + variables[(volunteer_id, second_id)]
                        <= 1
                    )

    coverage_weight = total_slots + 1
    model.Maximize(
        sum(
            (coverage_weight + int(pair in preferred_pairs)) * variable
            for pair, variable in variables.items()
        )
    )

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 42
    started = time.perf_counter()
    try:
        status_code = solver.Solve(model)
    except Exception as error:
        raise RuntimeError(f"OR-Tools CP-SAT failed while solving: {error}") from error
    elapsed_seconds = time.perf_counter() - started

    if status_code == cp_model.OPTIMAL:
        status = "optimal"
    elif status_code == cp_model.FEASIBLE:
        status = "feasible"
    else:
        status = "no_solution"

    assignments: list[tuple[str, str]] = []
    preference_count = 0
    if status in {"optimal", "feasible"}:
        for pair, variable in variables.items():
            if solver.Value(variable):
                assignments.append(pair)
                preference_count += int(pair in preferred_pairs)
    assignments.sort(key=lambda pair: (pair[1], pair[0]))

    return SolverResult(
        status=status,
        assignments=assignments,
        filled_slots=len(assignments),
        total_slots=total_slots,
        preference_count=preference_count,
        elapsed_seconds=elapsed_seconds,
    )
