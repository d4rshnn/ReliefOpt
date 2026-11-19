"""Local Streamlit interface for ShiftWise volunteer scheduling."""

from __future__ import annotations

import csv
import importlib
import io
import json
from pathlib import Path
from typing import Any

import streamlit as st

from shiftwise.metrics import calculate_metrics
from shiftwise.models import ShiftSlot, SolverResult, Volunteer
from shiftwise.validation import (
    ValidationError,
    validate_assignments,
    validate_scenario,
)


ROOT = Path(__file__).resolve().parent
SCENARIO_PATHS = {
    "Normal staffing": ROOT / "data" / "normal_staffing.json",
    "Limited staffing": ROOT / "data" / "limited_staffing.json",
}
SOLVER_MODULES = {
    "OR-Tools": "shiftwise.solver_ortools",
    "PuLP": "shiftwise.solver_pulp",
}


@st.cache_data
def load_scenario(path_string: str) -> dict[str, Any]:
    """Load and validate one bundled JSON scenario."""
    with Path(path_string).open(encoding="utf-8") as scenario_file:
        scenario = json.load(scenario_file)
    validate_scenario(scenario)
    return scenario


def to_contract_records(scenario: dict[str, Any]) -> tuple[list[Volunteer], list[ShiftSlot]]:
    """Convert JSON collections to the concrete shared model dataclasses."""
    volunteers = [
        Volunteer(
            id=row["id"],
            name=row["name"],
            skills=row["skills"],
            available_slot_ids=row["available_slot_ids"],
            max_assignments=row["max_assignments"],
            preferred_slot_ids=row["preferred_slot_ids"],
        )
        for row in scenario["volunteers"]
    ]
    slots = [ShiftSlot(**row) for row in scenario["slots"]]
    return volunteers, slots


def format_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def result_rows(
    scenario: dict[str, Any], result: SolverResult, solver_name: str
) -> list[dict[str, str]]:
    """Create one CSV/display row per slot, retaining uncovered positions."""
    volunteers_by_id = {volunteer["id"]: volunteer for volunteer in scenario["volunteers"]}
    slots_by_id = {slot["id"]: slot for slot in scenario["slots"]}
    assigned_by_slot: dict[str, str] = {}
    for volunteer_id, slot_id in result.assignments:
        if volunteer_id not in volunteers_by_id or slot_id not in slots_by_id:
            raise ValidationError(["Solver result references an unknown volunteer or slot ID."])
        if slot_id in assigned_by_slot:
            raise ValidationError([f"Solver assigned slot {slot_id!r} more than once."])
        assigned_by_slot[slot_id] = volunteer_id

    rows: list[dict[str, str]] = []
    for slot in scenario["slots"]:
        volunteer_id = assigned_by_slot.get(slot["id"], "")
        volunteer_name = volunteers_by_id[volunteer_id]["name"] if volunteer_id else "Unfilled"
        rows.append({
            "Solver": solver_name,
            "Slot": slot["id"],
            "Role": slot["role"],
            "Time": f"{format_time(slot['start_time'])}–{format_time(slot['end_time'])}",
            "Required skill": slot["required_skill"] or "None",
            "Volunteer": volunteer_name,
            "Volunteer ID": volunteer_id,
        })
    return rows


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _load_solver(solver_name: str):
    module_path = SOLVER_MODULES[solver_name]
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as error:
        missing = error.name or module_path
        raise RuntimeError(
            f"{solver_name} is unavailable because {missing!r} is not installed or present. "
            "Install the project dependencies and confirm the solver module is in the repository."
        ) from error
    return module.solve


def run_solvers(scenario: dict[str, Any], solver_choice: str) -> dict[str, SolverResult]:
    """Run selected solver(s) and validate every returned roster before display."""
    validate_scenario(scenario)
    volunteers, slots = to_contract_records(scenario)
    names = list(SOLVER_MODULES) if solver_choice == "Compare both" else [solver_choice]
    results: dict[str, SolverResult] = {}
    for solver_name in names:
        result = _load_solver(solver_name)(volunteers, slots)
        if not isinstance(result, SolverResult):
            raise TypeError(f"{solver_name} returned {type(result).__name__}, not shared SolverResult.")
        validate_assignments(volunteers, slots, result.assignments)
        metrics = calculate_metrics(volunteers, slots, result.assignments)
        if (
            result.filled_slots != metrics["filled_slots"]
            or result.total_slots != metrics["total_slots"]
            or result.preference_count != metrics["preference_count"]
        ):
            raise ValidationError([f"{solver_name} result counts do not match its assignments."])
        results[solver_name] = result
    return results


def _render_solver_result(
    scenario: dict[str, Any], result: SolverResult, solver_name: str
) -> list[dict[str, str]]:
    rows = result_rows(scenario, result, solver_name)
    percentage = (result.filled_slots / result.total_slots * 100) if result.total_slots else 0.0
    st.subheader(f"{solver_name} roster")
    coverage_col, percent_col, preference_col, elapsed_col = st.columns(4)
    coverage_col.metric("Coverage", f"{result.filled_slots}/{result.total_slots}")
    percent_col.metric("Coverage rate", f"{percentage:.1f}%")
    preference_col.metric("Preference matches", str(result.preference_count))
    elapsed_col.metric("Solver time", f"{result.elapsed_seconds:.4f} s")
    st.caption(f"Status: {result.status}")
    st.dataframe(
        [{key: value for key, value in row.items() if key != "Solver"} for row in rows],
        width="stretch",
        hide_index=True,
    )

    uncovered = [row["Slot"] for row in rows if row["Volunteer"] == "Unfilled"]
    if uncovered:
        st.warning("Uncovered slots: " + ", ".join(uncovered))
    else:
        st.success("All slots are covered.")

    volunteers, _slots = to_contract_records(scenario)
    metrics = calculate_metrics(volunteers, _slots, result.assignments)
    counts = metrics["assignment_counts"]
    st.markdown("**Assignments per volunteer**")
    st.dataframe(
        [
            {
                "Volunteer": volunteer.name,
                "Assignments": counts[volunteer.id],
                "Limit": volunteer.max_assignments,
            }
            for volunteer in volunteers
        ],
        width="stretch",
        hide_index=True,
    )
    return rows


def main() -> None:
    st.set_page_config(page_title="ShiftWise", page_icon="🗓️", layout="wide")
    st.title("ShiftWise: Volunteer Shift Scheduler")
    st.write("Build a coverage-first roster for a fictional Campus Tech Fest.")

    scenario_label = st.selectbox("Staffing scenario", list(SCENARIO_PATHS))
    solver_choice = st.selectbox("Solver", ["OR-Tools", "PuLP", "Compare both"])
    try:
        scenario = load_scenario(str(SCENARIO_PATHS[scenario_label]))
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        st.error(f"The selected scenario could not be loaded: {error}")
        return

    st.caption(scenario.get("description", ""))
    st.write(f"**{len(scenario['volunteers'])} volunteers · {len(scenario['slots'])} slots**")

    if st.button("Run optimization", type="primary"):
        st.session_state.pop("last_results", None)
        st.session_state.pop("last_context", None)
        try:
            st.session_state["last_results"] = run_solvers(scenario, solver_choice)
            st.session_state["last_context"] = (scenario["scenario_id"], solver_choice)
        except (ValidationError, RuntimeError, TypeError, ValueError) as error:
            st.error(f"Optimization could not be completed: {error}")
        except Exception as error:  # Surface unexpected backend failures without hiding them.
            st.error(f"{solver_choice} failed ({type(error).__name__}): {error}")

    context = (scenario["scenario_id"], solver_choice)
    results = st.session_state.get("last_results", {})
    if st.session_state.get("last_context") != context:
        results = {}

    if results:
        csv_rows: list[dict[str, str]] = []
        if len(results) == 2:
            st.subheader("Solver comparison")
            st.dataframe(
                [
                    {
                        "Solver": name,
                        "Status": result.status,
                        "Filled slots": f"{result.filled_slots}/{result.total_slots}",
                        "Preference matches": result.preference_count,
                        "Elapsed seconds": result.elapsed_seconds,
                    }
                    for name, result in results.items()
                ],
                width="stretch",
                hide_index=True,
            )
            columns = st.columns(2)
            for column, (name, result) in zip(columns, results.items()):
                with column:
                    csv_rows.extend(_render_solver_result(scenario, result, name))
        else:
            name, result = next(iter(results.items()))
            csv_rows = _render_solver_result(scenario, result, name)

        st.download_button(
            "Download roster as CSV",
            data=csv_bytes(csv_rows),
            file_name=f"{scenario['scenario_id']}_roster.csv",
            mime="text/csv",
        )

    with st.expander("About this model"):
        st.write(
            "Volunteers and individual slots form the two sides of a bipartite graph. "
            "Only available, skill-qualified pairs are eligible. The optimizer enforces "
            "assignment caps and half-open overlap conflicts, maximizes coverage first, "
            "then uses preferences to break ties."
        )


if __name__ == "__main__":
    main()
