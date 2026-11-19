"""Shared data structures for the ShiftWise volunteer scheduler.

Collection fields are normalized to ``frozenset[str]`` at construction time.
The solver-facing field names and meanings match PROJECT_BRIEF.md.
"""

from __future__ import annotations

from dataclasses import dataclass


def _string_frozenset(values, field_name: str) -> frozenset[str]:
    if not isinstance(values, (set, frozenset, list, tuple)):
        raise TypeError(f"{field_name} must be a set or list of strings.")
    items = list(values)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError(f"{field_name} must contain only nonempty strings.")
    if len(items) != len(set(items)):
        raise ValueError(f"{field_name} must not contain duplicate values.")
    return frozenset(items)


@dataclass(frozen=True)
class Volunteer:
    """A volunteer and their event-level constraints and preferences."""

    id: str
    name: str
    skills: frozenset[str] | set[str] | list[str]
    available_slot_ids: frozenset[str] | set[str] | list[str]
    max_assignments: int
    preferred_slot_ids: frozenset[str] | set[str] | list[str]

    def __post_init__(self) -> None:
        for field_name in ("skills", "available_slot_ids", "preferred_slot_ids"):
            object.__setattr__(self, field_name, _string_frozenset(getattr(self, field_name), field_name))


@dataclass(frozen=True)
class ShiftSlot:
    """One individual role position, measured in minutes after midnight."""

    id: str
    role: str
    start_time: int
    end_time: int
    required_skill: str | None


@dataclass(frozen=True)
class SolverResult:
    """Normalized outcome returned by either optimization backend."""

    status: str  # "optimal", "feasible", or "no_solution"
    assignments: list[tuple[str, str]]  # (volunteer_id, slot_id)
    filled_slots: int
    total_slots: int
    preference_count: int
    elapsed_seconds: float

    def __post_init__(self) -> None:
        if self.status not in {"optimal", "feasible", "no_solution"}:
            raise ValueError("status must be optimal, feasible, or no_solution.")
        normalized = [tuple(pair) for pair in self.assignments]
        if any(len(pair) != 2 or any(not isinstance(value, str) for value in pair) for pair in normalized):
            raise ValueError("assignments must contain (volunteer_id, slot_id) string pairs.")
        object.__setattr__(self, "assignments", normalized)
        for field_name in ("filled_slots", "total_slots", "preference_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a nonnegative integer.")
        if self.filled_slots > self.total_slots:
            raise ValueError("filled_slots cannot exceed total_slots.")
        if self.preference_count > self.filled_slots:
            raise ValueError("preference_count cannot exceed filled_slots.")
        if len(normalized) != self.filled_slots:
            raise ValueError("filled_slots must equal the number of returned assignments.")
        if len({slot_id for _volunteer_id, slot_id in normalized}) != len(normalized):
            raise ValueError("A slot may appear at most once in assignments.")
        if isinstance(self.elapsed_seconds, bool) or not isinstance(self.elapsed_seconds, (int, float)) or self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be a nonnegative number.")

    def __getitem__(self, field: str):
        """Allow dictionary-style field access for compatibility with the app."""
        return getattr(self, field)
