"""OR-Tools CP-SAT solver implementation for ShiftWise."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable

from ortools.sat.python import cp_model


@dataclass
class SolverResult:
    """Normalized solver outcome adhering to the ShiftWise shared contract."""

    status: str  # "optimal", "feasible", or "no_solution"
    assignments: list[tuple[str, str]]  # list of (volunteer_id, slot_id)
    filled_slots: int
    total_slots: int
    preference_count: int
    elapsed_seconds: float

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Safely extract field from dataclass, SimpleNamespace, or dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def slots_overlap(s1: Any, s2: Any) -> bool:
    """Check if two half-open slot intervals [start, end) overlap.

    Two slots overlap when start1 < end2 and start2 < end1.
    Adjacent slots where end1 == start2 do not overlap.
    """
    start1 = int(_get_attr(s1, "start_time", 0))
    end1 = int(_get_attr(s1, "end_time", 0))
    start2 = int(_get_attr(s2, "start_time", 0))
    end2 = int(_get_attr(s2, "end_time", 0))
    return start1 < end2 and start2 < end1


def solve(volunteers: Iterable[Any], slots: Iterable[Any]) -> SolverResult:
    """Solve the volunteer assignment problem using OR-Tools CP-SAT.

    Parameters
    ----------
    volunteers : Iterable[Any]
        Collection of volunteer records with attributes/keys:
        - id: str
        - name: str
        - skills: set[str] | list[str]
        - available_slot_ids: set[str] | list[str]
        - max_assignments: int
        - preferred_slot_ids: set[str] | list[str]
    slots : Iterable[Any]
        Collection of shift slot records with attributes/keys:
        - id: str
        - role: str
        - start_time: int (minutes after midnight)
        - end_time: int (minutes after midnight; end_time > start_time)
        - required_skill: str | None

    Returns
    -------
    SolverResult
        Result containing normalized status, assignment pairs, filled slots,
        total slots, preference count, and elapsed seconds.
    """
    start_perf = time.perf_counter()

    volunteer_list = list(volunteers)
    slot_list = list(slots)
    total_slots = len(slot_list)

    if total_slots == 0:
        elapsed = time.perf_counter() - start_perf
        return SolverResult(
            status="optimal",
            assignments=[],
            filled_slots=0,
            total_slots=0,
            preference_count=0,
            elapsed_seconds=elapsed,
        )

    model = cp_model.CpModel()

    # Pre-process slots
    slot_by_id: dict[str, Any] = {}
    for slot in slot_list:
        s_id = str(_get_attr(slot, "id"))
        slot_by_id[s_id] = slot

    # Decision variables: x[(v_id, s_id)] defined ONLY for eligible pairs
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    volunteer_eligible_slots: dict[str, list[str]] = {
        str(_get_attr(v, "id")): [] for v in volunteer_list
    }
    slot_eligible_volunteers: dict[str, list[str]] = {s_id: [] for s_id in slot_by_id}
    preferred_pairs: set[tuple[str, str]] = set()

    for volunteer in volunteer_list:
        v_id = str(_get_attr(volunteer, "id"))
        raw_skills = _get_attr(volunteer, "skills", [])
        v_skills = set(raw_skills) if raw_skills else set()

        raw_avail = _get_attr(volunteer, "available_slot_ids", [])
        v_avail = set(raw_avail) if raw_avail else set()

        raw_pref = _get_attr(volunteer, "preferred_slot_ids", [])
        v_pref = set(raw_pref) if raw_pref else set()

        for s_id, slot in slot_by_id.items():
            # Check availability
            if s_id not in v_avail:
                continue

            # Check required skill
            req_skill = _get_attr(slot, "required_skill")
            if req_skill is not None and str(req_skill).strip():
                if req_skill not in v_skills:
                    continue

            # Pair is eligible -> create binary variable
            var = model.NewBoolVar(f"x_{v_id}_{s_id}")
            x[(v_id, s_id)] = var
            volunteer_eligible_slots[v_id].append(s_id)
            slot_eligible_volunteers[s_id].append(v_id)

            if s_id in v_pref:
                preferred_pairs.add((v_id, s_id))

    # Constraint 1: At most one volunteer per slot (partial coverage allowed)
    for s_id, eligible_v_ids in slot_eligible_volunteers.items():
        if eligible_v_ids:
            model.AddAtMostOne([x[(v_id, s_id)] for v_id in eligible_v_ids])

    # Constraint 2: Volunteer assignment limit
    for volunteer in volunteer_list:
        v_id = str(_get_attr(volunteer, "id"))
        max_assignments = int(_get_attr(volunteer, "max_assignments", 0))
        eligible_s_ids = volunteer_eligible_slots[v_id]
        if eligible_s_ids:
            model.Add(sum(x[(v_id, s_id)] for s_id in eligible_s_ids) <= max_assignments)

    # Constraint 3: No overlapping shifts for the same volunteer
    for volunteer in volunteer_list:
        v_id = str(_get_attr(volunteer, "id"))
        eligible_s_ids = volunteer_eligible_slots[v_id]
        n_eligible = len(eligible_s_ids)
        if n_eligible > 1:
            for i in range(n_eligible):
                s1_id = eligible_s_ids[i]
                s1 = slot_by_id[s1_id]
                for j in range(i + 1, n_eligible):
                    s2_id = eligible_s_ids[j]
                    s2 = slot_by_id[s2_id]
                    if slots_overlap(s1, s2):
                        model.Add(x[(v_id, s1_id)] + x[(v_id, s2_id)] <= 1)

    # Objective: Maximize (|S| + 1) * filled_slots + preference_matches
    # Since each slot can be filled at most once, preference_matches <= |S|.
    # Therefore, each filled slot weight (|S| + 1) dominates any preference loss.
    coverage_weight = total_slots + 1
    objective_terms: list[Any] = []
    for (v_id, s_id), var in x.items():
        weight = coverage_weight + (1 if (v_id, s_id) in preferred_pairs else 0)
        objective_terms.append(weight * var)

    if objective_terms:
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = 42

    status_code = solver.Solve(model)
    total_elapsed = time.perf_counter() - start_perf

    # Status normalization
    if status_code == cp_model.OPTIMAL:
        normalized_status = "optimal"
    elif status_code == cp_model.FEASIBLE:
        normalized_status = "feasible"
    else:
        normalized_status = "no_solution"

    assignments: list[tuple[str, str]] = []
    preference_count = 0

    if normalized_status in ("optimal", "feasible"):
        for (v_id, s_id), var in x.items():
            if solver.Value(var) == 1:
                assignments.append((v_id, s_id))
                if (v_id, s_id) in preferred_pairs:
                    preference_count += 1

        # Sort assignments by slot_id for clean, deterministic output
        assignments.sort(key=lambda pair: pair[1])

    filled_slots = len(assignments)

    return SolverResult(
        status=normalized_status,
        assignments=assignments,
        filled_slots=filled_slots,
        total_slots=total_slots,
        preference_count=preference_count,
        elapsed_seconds=round(total_elapsed, 6),
    )
