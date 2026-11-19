"""Validation for ShiftWise volunteer and slot inputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class ValidationError(ValueError):
    """Raised when one or more input records violate the shared contract."""

    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("Input validation failed:\n- " + "\n- ".join(self.errors))


def _field(record: Any, name: str, default: Any = ...):
    if isinstance(record, Mapping):
        if name in record:
            return record[name]
    elif hasattr(record, name):
        return getattr(record, name)
    if default is ...:
        raise KeyError(name)
    return default


def _as_records(records: Any, label: str, errors: list[str]) -> list[Any]:
    if isinstance(records, (str, bytes, Mapping)) or not isinstance(records, Iterable):
        errors.append(f"{label} must be a collection of records.")
        return []
    return list(records)


def _required_fields(record: Any, required: tuple[str, ...], owner: str, errors: list[str]) -> bool:
    missing = [name for name in required if _field(record, name, None) is None and not _has_field(record, name)]
    if missing:
        errors.append(f"{owner} is missing required field(s): {', '.join(missing)}.")
        return False
    return True


def _has_field(record: Any, name: str) -> bool:
    return name in record if isinstance(record, Mapping) else hasattr(record, name)


def _nonempty_string(value: Any, owner: str, field: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{owner}.{field} must be a nonempty string.")
        return False
    return True


def _string_collection(value: Any, owner: str, field: str, errors: list[str]) -> set[str] | None:
    if isinstance(value, (str, bytes)) or not isinstance(value, (set, frozenset, list, tuple)):
        errors.append(f"{owner}.{field} must be a set or list of strings.")
        return None
    values = list(value)
    if any(not isinstance(item, str) or not item.strip() for item in values):
        errors.append(f"{owner}.{field} must contain only nonempty strings.")
        return None
    if len(values) != len(set(values)):
        errors.append(f"{owner}.{field} contains duplicate values.")
    return set(values)


def validate_inputs(volunteers: Iterable[Any], slots: Iterable[Any], *, require_slots: bool = False) -> None:
    """Validate volunteer and slot records; raise :class:`ValidationError` on defects.

    Accepts mappings (for JSON records) or attribute-based objects (for the
    shared dataclasses and the app's temporary SimpleNamespace adapter).
    ``require_slots=True`` is appropriate for a runnable demo scenario.
    """
    errors: list[str] = []
    volunteer_records = _as_records(volunteers, "volunteers", errors)
    slot_records = _as_records(slots, "slots", errors)
    if require_slots and not slot_records:
        errors.append("At least one slot is required for a demo scenario.")

    slot_ids: list[str] = []
    for index, slot in enumerate(slot_records):
        owner = f"slot[{index}]"
        required = ("id", "role", "start_time", "end_time", "required_skill")
        if not _required_fields(slot, required, owner, errors):
            continue
        slot_id = _field(slot, "id")
        if _nonempty_string(slot_id, owner, "id", errors):
            slot_ids.append(slot_id)
        _nonempty_string(_field(slot, "role"), owner, "role", errors)
        start, end = _field(slot, "start_time"), _field(slot, "end_time")
        if isinstance(start, bool) or not isinstance(start, int) or isinstance(end, bool) or not isinstance(end, int):
            errors.append(f"{owner} start_time and end_time must be integer minutes after midnight.")
        elif start < 0 or end < 0 or end <= start:
            errors.append(f"{owner} must have nonnegative times with end_time greater than start_time.")
        skill = _field(slot, "required_skill")
        if skill is not None and (not isinstance(skill, str) or not skill.strip()):
            errors.append(f"{owner}.required_skill must be None or a nonempty string.")

    duplicate_slot_ids = sorted({item for item in slot_ids if slot_ids.count(item) > 1})
    if duplicate_slot_ids:
        errors.append("Duplicate slot ID(s): " + ", ".join(duplicate_slot_ids) + ".")
    known_slot_ids = set(slot_ids)

    volunteer_ids: list[str] = []
    for index, volunteer in enumerate(volunteer_records):
        owner = f"volunteer[{index}]"
        required = ("id", "name", "skills", "available_slot_ids", "max_assignments", "preferred_slot_ids")
        if not _required_fields(volunteer, required, owner, errors):
            continue
        volunteer_id = _field(volunteer, "id")
        if _nonempty_string(volunteer_id, owner, "id", errors):
            volunteer_ids.append(volunteer_id)
        _nonempty_string(_field(volunteer, "name"), owner, "name", errors)

        cap = _field(volunteer, "max_assignments")
        if isinstance(cap, bool) or not isinstance(cap, int) or cap < 0:
            errors.append(f"{owner}.max_assignments must be a nonnegative integer.")

        skills = _string_collection(_field(volunteer, "skills"), owner, "skills", errors)
        available = _string_collection(_field(volunteer, "available_slot_ids"), owner, "available_slot_ids", errors)
        preferred = _string_collection(_field(volunteer, "preferred_slot_ids"), owner, "preferred_slot_ids", errors)
        for field_name, references in (("available_slot_ids", available), ("preferred_slot_ids", preferred)):
            if references is not None:
                unknown = sorted(references - known_slot_ids)
                if unknown:
                    errors.append(f"{owner}.{field_name} references unknown slot ID(s): {', '.join(unknown)}.")

    duplicate_volunteer_ids = sorted({item for item in volunteer_ids if volunteer_ids.count(item) > 1})
    if duplicate_volunteer_ids:
        errors.append("Duplicate volunteer ID(s): " + ", ".join(duplicate_volunteer_ids) + ".")

    if errors:
        raise ValidationError(errors)


def validate_scenario(scenario: Mapping[str, Any]) -> None:
    """Validate JSON scenario metadata and its volunteer/slot collections."""
    errors: list[str] = []
    if not isinstance(scenario, Mapping):
        raise ValidationError(["scenario must be a mapping/object."])
    for field in ("scenario_id", "label"):
        if field not in scenario:
            errors.append(f"scenario is missing required field {field!r}.")
        elif not isinstance(scenario[field], str) or not scenario[field].strip():
            errors.append(f"scenario.{field} must be a nonempty string.")
    for field in ("volunteers", "slots"):
        if field not in scenario:
            errors.append(f"scenario is missing required field {field!r}.")
    if errors:
        raise ValidationError(errors)
    validate_inputs(scenario["volunteers"], scenario["slots"], require_slots=True)


def validate_assignments(volunteers: Iterable[Any], slots: Iterable[Any], assignments: Iterable[tuple[str, str]]) -> None:
    """Validate a solver roster against all hard assignment constraints.

    Checks pair shape, known IDs, eligibility, one volunteer per slot,
    volunteer assignment caps, and half-open time conflicts.
    """
    from .helpers import is_eligible, slots_overlap

    volunteer_records, slot_records = list(volunteers), list(slots)
    validate_inputs(volunteer_records, slot_records)
    volunteer_by_id = {_field(volunteer, "id"): volunteer for volunteer in volunteer_records}
    slot_by_id = {_field(slot, "id"): slot for slot in slot_records}
    errors: list[str] = []
    assigned_slots: dict[str, str] = {}
    assigned_by_volunteer: dict[str, list[str]] = {volunteer_id: [] for volunteer_id in volunteer_by_id}
    seen_pairs: set[tuple[str, str]] = set()

    for index, pair in enumerate(assignments):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            errors.append(f"assignment[{index}] must be a (volunteer_id, slot_id) pair.")
            continue
        volunteer_id, slot_id = pair
        if not isinstance(volunteer_id, str) or not isinstance(slot_id, str):
            errors.append(f"assignment[{index}] IDs must both be strings.")
            continue
        if (volunteer_id, slot_id) in seen_pairs:
            errors.append(f"Duplicate assignment pair ({volunteer_id!r}, {slot_id!r}).")
            continue
        seen_pairs.add((volunteer_id, slot_id))
        volunteer = volunteer_by_id.get(volunteer_id)
        slot = slot_by_id.get(slot_id)
        if volunteer is None:
            errors.append(f"Assignment references unknown volunteer ID {volunteer_id!r}.")
            continue
        if slot is None:
            errors.append(f"Assignment references unknown slot ID {slot_id!r}.")
            continue
        if slot_id in assigned_slots:
            errors.append(
                f"Slot {slot_id!r} is assigned to both {assigned_slots[slot_id]!r} and {volunteer_id!r}."
            )
        else:
            assigned_slots[slot_id] = volunteer_id
        if not is_eligible(volunteer, slot):
            errors.append(f"Volunteer {volunteer_id!r} is not eligible for slot {slot_id!r} (availability/skill).")
        assigned_by_volunteer[volunteer_id].append(slot_id)

    for volunteer_id, volunteer_slot_ids in assigned_by_volunteer.items():
        volunteer = volunteer_by_id[volunteer_id]
        cap = _field(volunteer, "max_assignments")
        if len(volunteer_slot_ids) > cap:
            errors.append(
                f"Volunteer {volunteer_id!r} has {len(volunteer_slot_ids)} assignments, exceeding cap {cap}."
            )
        for index, first_id in enumerate(volunteer_slot_ids):
            for second_id in volunteer_slot_ids[index + 1:]:
                if slots_overlap(slot_by_id[first_id], slot_by_id[second_id]):
                    errors.append(
                        f"Volunteer {volunteer_id!r} has overlapping slots {first_id!r} and {second_id!r}."
                    )

    if errors:
        raise ValidationError(errors)
