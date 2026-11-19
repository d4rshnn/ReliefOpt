"""Common eligibility and time-conflict helpers for ShiftWise."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get(record: Any, field: str):
    return record[field] if isinstance(record, Mapping) else getattr(record, field)


def is_eligible(volunteer: Any, slot: Any) -> bool:
    """Return whether a volunteer is available and meets a slot's skill need."""
    if _get(slot, "id") not in _get(volunteer, "available_slot_ids"):
        return False
    required_skill = _get(slot, "required_skill")
    return required_skill is None or required_skill in _get(volunteer, "skills")


def slots_overlap(slot_a: Any, slot_b: Any) -> bool:
    """Return whether two half-open intervals ``[start, end)`` overlap.

    Adjacent intervals such as 09:00–10:00 and 10:00–11:00 do not overlap.
    """
    start_a, end_a = _get(slot_a, "start_time"), _get(slot_a, "end_time")
    start_b, end_b = _get(slot_b, "start_time"), _get(slot_b, "end_time")
    return start_a < end_b and start_b < end_a


# Short alias for callers that prefer the generic name.
overlaps = slots_overlap
