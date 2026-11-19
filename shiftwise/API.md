# ShiftWise shared Python API

This note freezes the concrete representation for the shared layer. It follows the field names and semantics in `PROJECT_BRIEF.md`; it does not define or create event records.

## Record types

Import `Volunteer`, `ShiftSlot`, and `SolverResult` from `shiftwise.models`.

- `Volunteer(id: str, name: str, skills, available_slot_ids, max_assignments: int, preferred_slot_ids)`
- `ShiftSlot(id: str, role: str, start_time: int, end_time: int, required_skill: str | None)`
- `SolverResult(status: str, assignments: list[tuple[str, str]], filled_slots: int, total_slots: int, preference_count: int, elapsed_seconds: float)`

The three volunteer collections accept a `set[str]`, `list[str]`, or `frozenset[str]` and are normalized to `frozenset[str]` in the dataclass. Values must be nonempty strings and duplicates in list-like inputs are rejected. The solver-facing field names remain unchanged. Slot times are integer minutes after midnight; intervals are half-open `[start_time, end_time)`.

`SolverResult.status` is one of `optimal`, `feasible`, or `no_solution`. Assignment pairs are `(volunteer_id, slot_id)`. `SolverResult` supports both attribute access and `result["field"]` for the current app's result-reader compatibility.

## Validation API

- `validate_inputs(volunteers, slots, *, require_slots=False) -> None`
- `validate_scenario(scenario: Mapping[str, Any]) -> None`
- `validate_assignments(volunteers, slots, assignments) -> None`: checks returned pairs, IDs, eligibility, one-per-slot, caps, and overlap constraints.
- `ValidationError(ValueError)` exposes an `.errors` tuple and a combined actionable message.

Validation accepts JSON dictionaries or attribute-based records. `validate_assignments` is the post-solve integrity check; call it before displaying/exporting a roster. It checks required fields, nonempty IDs/names/roles/skills, duplicate IDs and collection values, collection types, unknown availability/preference slot references, nonnegative integer caps, integer nonnegative times with `end_time > start_time`, and `required_skill` as `None` or a nonempty string. `validate_scenario` additionally requires nonempty `scenario_id` and `label` and at least one slot.

## Shared helper API

- `is_eligible(volunteer, slot) -> bool`: volunteer must list the slot in `available_slot_ids` and possess `required_skill`, unless it is `None`.
- `slots_overlap(slot_a, slot_b) -> bool` (alias: `overlaps`): returns `start_a < end_b and start_b < end_a`; adjacent shifts do not overlap.

## Metrics API

- `uncovered_slot_ids(slots, assignments) -> list[str]`
- `coverage_percentage(filled_slots, total_slots) -> float` (returns `0.0` when total is zero)
- `preference_matches(volunteers, assignments) -> int`
- `assignment_counts(volunteers, assignments) -> dict[str, int]`
- `calculate_metrics(volunteers, slots, assignments) -> dict[str, Any]`, combining the above into `filled_slots`, `total_slots`, `coverage_percentage`, `uncovered_slot_ids`, `preference_count`, and `assignment_counts`.

Both solver authors can import `SolverResult` and the helpers directly. Validation should run before invoking a solver; metrics summarize a returned roster and do not replace solver feasibility checks.
