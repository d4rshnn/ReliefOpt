"""Roster metrics shared by the app, solvers, and demo checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _get(record: Any, field: str):
    return record[field] if isinstance(record, Mapping) else getattr(record, field)


def uncovered_slot_ids(slots: Iterable[Any], assignments: Iterable[tuple[str, str]]) -> list[str]:
    """Return slot IDs with no assigned volunteer, preserving slot order."""
    assigned = {slot_id for _volunteer_id, slot_id in assignments}
    return [slot_id for slot_id in (_get(slot, "id") for slot in slots) if slot_id not in assigned]


def coverage_percentage(filled_slots: int, total_slots: int) -> float:
    """Return coverage as a percentage; zero slots safely produce 0.0."""
    if total_slots < 0 or filled_slots < 0 or filled_slots > total_slots:
        raise ValueError("Require 0 <= filled_slots <= total_slots.")
    if total_slots == 0:
        return 0.0
    return filled_slots / total_slots * 100.0


def preference_matches(
    volunteers: Iterable[Any], assignments: Iterable[tuple[str, str]]
) -> int:
    """Count assignments where that volunteer listed the slot as preferred."""
    preferred_by_volunteer = {
        _get(volunteer, "id"): set(_get(volunteer, "preferred_slot_ids"))
        for volunteer in volunteers
    }
    return sum(
        1 for volunteer_id, slot_id in assignments
        if volunteer_id in preferred_by_volunteer and slot_id in preferred_by_volunteer[volunteer_id]
    )


def assignment_counts(
    volunteers: Iterable[Any], assignments: Iterable[tuple[str, str]]
) -> dict[str, int]:
    """Return assignment counts for every volunteer, including zero counts."""
    counts = {_get(volunteer, "id"): 0 for volunteer in volunteers}
    for volunteer_id, _slot_id in assignments:
        if volunteer_id in counts:
            counts[volunteer_id] += 1
    return counts


def calculate_metrics(volunteers: Iterable[Any], slots: Iterable[Any], assignments: Iterable[tuple[str, str]]) -> dict[str, Any]:
    """Calculate the common roster summary from input records and assignment pairs."""
    volunteer_list, slot_list, assignment_list = list(volunteers), list(slots), list(assignments)
    filled = len({slot_id for _volunteer_id, slot_id in assignment_list})
    return {
        "filled_slots": filled,
        "total_slots": len(slot_list),
        "coverage_percentage": coverage_percentage(filled, len(slot_list)),
        "uncovered_slot_ids": uncovered_slot_ids(slot_list, assignment_list),
        "preference_count": preference_matches(volunteer_list, assignment_list),
        "assignment_counts": assignment_counts(volunteer_list, assignment_list),
    }
