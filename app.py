"""Local ReliefOpt command center for deterministic incident allocation."""

from __future__ import annotations

import csv
import html
import importlib
import io
import json
from pathlib import Path
from typing import Any

import streamlit as st

from shiftwise.metrics import calculate_metrics
from shiftwise.models import ShiftSlot, SolverResult, Volunteer
from shiftwise.validation import ValidationError, validate_assignments, validate_scenario


ROOT = Path(__file__).resolve().parent
SCENARIO_PATHS = {
    "Normal response capacity": ROOT / "data" / "normal_staffing.json",
    "Catastrophic shortage": ROOT / "data" / "limited_staffing.json",
}
SOLVER_MODULES = {
    "OR-Tools CP-SAT": "shiftwise.solver_ortools",
    "PuLP": "shiftwise.solver_pulp",
}
TRIAGE = {
    "RED": {"label": "RED · Critical", "symbol": "🔴", "class": "red"},
    "YELLOW": {"label": "YELLOW · Urgent", "symbol": "🟠", "class": "yellow"},
    "GREEN": {"label": "GREEN · Routine", "symbol": "🟡", "class": "green"},
}


def _validate_triage_metadata(scenario: dict[str, Any]) -> None:
    mapping = scenario.get("incident_triage")
    incident_ids = {slot["id"] for slot in scenario["slots"]}
    if not isinstance(mapping, dict) or set(mapping) != incident_ids:
        raise ValidationError(["incident_triage must label every incident ID exactly once."])
    invalid = sorted(incident_id for incident_id, level in mapping.items() if level not in TRIAGE)
    if invalid:
        raise ValidationError([f"Unknown triage level for incident(s): {', '.join(invalid)}."])


@st.cache_data
def load_scenario(path_string: str) -> dict[str, Any]:
    """Load and validate one bundled resource/incident scenario."""
    with Path(path_string).open(encoding="utf-8") as scenario_file:
        scenario = json.load(scenario_file)
    validate_scenario(scenario)
    _validate_triage_metadata(scenario)
    return scenario


def to_contract_records(scenario: dict[str, Any]) -> tuple[list[Volunteer], list[ShiftSlot]]:
    """Convert the JSON resource and incident records to shared solver types."""
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
    """Build one dispatch row per incident, including unattended incidents."""
    volunteers_by_id = {unit["id"]: unit for unit in scenario["volunteers"]}
    slots_by_id = {slot["id"]: slot for slot in scenario["slots"]}
    assigned_by_slot: dict[str, str] = {}
    for resource_id, incident_id in result.assignments:
        if resource_id not in volunteers_by_id or incident_id not in slots_by_id:
            raise ValidationError(["Solver result references an unknown resource or incident ID."])
        if incident_id in assigned_by_slot:
            raise ValidationError([f"Solver assigned incident {incident_id!r} more than once."])
        assigned_by_slot[incident_id] = resource_id

    rows: list[dict[str, str]] = []
    for incident in scenario["slots"]:
        incident_id = incident["id"]
        resource_id = assigned_by_slot.get(incident_id, "")
        resource_name = volunteers_by_id[resource_id]["name"] if resource_id else "UNATTENDED"
        triage = TRIAGE[scenario["incident_triage"][incident_id]]
        rows.append({
            "Solver": solver_name,
            "Triage": f"{triage['symbol']} {triage['label']}",
            "Incident": incident_id,
            "Role": incident["role"],
            "Time": f"{format_time(incident['start_time'])}–{format_time(incident['end_time'])}",
            "Required capability": incident["required_skill"] or "General response",
            "Response unit": resource_name,
            "Resource ID": resource_id,
            "Dispatch status": "DISPATCHED" if resource_id else "UNATTENDED",
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
    try:
        module = importlib.import_module(SOLVER_MODULES[solver_name])
    except ModuleNotFoundError as error:
        missing = error.name or SOLVER_MODULES[solver_name]
        raise RuntimeError(
            f"{solver_name} is unavailable because {missing!r} is not installed or present. "
            "Install project dependencies and confirm the solver module is available."
        ) from error
    return module.solve


def run_solvers(scenario: dict[str, Any], solver_choice: str) -> dict[str, SolverResult]:
    """Run selected solver(s) and validate every allocation before display."""
    validate_scenario(scenario)
    _validate_triage_metadata(scenario)
    resources, incidents = to_contract_records(scenario)
    names = list(SOLVER_MODULES) if solver_choice == "Compare both" else [solver_choice]
    results: dict[str, SolverResult] = {}
    for name in names:
        result = _load_solver(name)(resources, incidents)
        if not isinstance(result, SolverResult):
            raise TypeError(f"{name} returned {type(result).__name__}, not shared SolverResult.")
        validate_assignments(resources, incidents, result.assignments)
        metrics = calculate_metrics(resources, incidents, result.assignments)
        if (
            result.filled_slots != metrics["filled_slots"]
            or result.total_slots != metrics["total_slots"]
            or result.preference_count != metrics["preference_count"]
        ):
            raise ValidationError([f"{name} result counts do not match its assignments."])
        results[name] = result
    return results


def _format_coverage(results: dict[str, SolverResult]) -> str:
    if len(results) == 1:
        result = next(iter(results.values()))
        return f"{result.filled_slots}/{result.total_slots}"
    coverages = {f"{result.filled_slots}/{result.total_slots}" for result in results.values()}
    if len(coverages) == 1:
        return f"{next(iter(coverages))} each"
    return " · ".join(f"{name}: {result.filled_slots}/{result.total_slots}" for name, result in results.items())


def _format_preferences(results: dict[str, SolverResult]) -> str:
    if len(results) == 1:
        return str(next(iter(results.values())).preference_count)
    return " · ".join(f"{name}: {result.preference_count}" for name, result in results.items())


def _format_latency(results: dict[str, SolverResult]) -> str:
    if len(results) == 1:
        result = next(iter(results.values()))
        return f"{result.elapsed_seconds * 1000:.1f} ms"
    return " · ".join(f"{name}: {result.elapsed_seconds * 1000:.1f} ms" for name, result in results.items())


def _render_kpi(label: str, value: str, note: str) -> None:
    st.markdown(
        "<div class='kpi-card'><div class='kpi-label'>" + html.escape(label)
        + "</div><div class='kpi-value'>" + html.escape(value)
        + "</div><div class='kpi-note'>" + html.escape(note) + "</div></div>",
        unsafe_allow_html=True,
    )


def _dispatch_cards(rows: list[dict[str, str]], scenario: dict[str, Any]) -> str:
    cards: list[str] = []
    for row in rows:
        level = scenario["incident_triage"][row["Incident"]]
        triage = TRIAGE[level]
        status_class = "unattended" if row["Dispatch status"] == "UNATTENDED" else "dispatched"
        cards.append(
            "<tr>"
            f"<td><span class='triage-badge {triage['class']}'>{html.escape(triage['symbol'])} {html.escape(triage['label'])}</span></td>"
            f"<td><strong>{html.escape(row['Incident'])}</strong><br><span class='muted'>{html.escape(row['Role'])}</span></td>"
            f"<td>{html.escape(row['Time'])}</td>"
            f"<td>{html.escape(row['Required capability'])}</td>"
            f"<td>{html.escape(row['Response unit'])}<br><span class='muted'>{html.escape(row['Resource ID'])}</span></td>"
            f"<td><span class='status-badge {status_class}'>{html.escape(row['Dispatch status'])}</span></td>"
            "</tr>"
        )
    return (
        "<div class='table-wrap'><table class='dispatch-table'><thead><tr>"
        "<th>Triage</th><th>Incident</th><th>Window</th><th>Required capability</th>"
        "<th>Response unit</th><th>Status</th></tr></thead><tbody>"
        + "".join(cards) + "</tbody></table></div>"
    )


def _render_dispatch_tab(scenario: dict[str, Any], results: dict[str, SolverResult]) -> list[dict[str, str]]:
    csv_rows: list[dict[str, str]] = []
    if not results:
        st.info("Choose a scenario and solver, then run allocation to build the dispatch manifest.")
        return csv_rows

    for name, result in results.items():
        rows = result_rows(scenario, result, name)
        uncovered = [row["Incident"] for row in rows if row["Dispatch status"] == "UNATTENDED"]
        if uncovered:
            st.error("⚠️ UNATTENDED INCIDENTS — " + ", ".join(uncovered))
        else:
            st.success(f"{name}: all incidents have a response unit.")
        if len(results) > 1:
            st.markdown(f"#### {name} manifest")
        st.markdown(_dispatch_cards(rows, scenario), unsafe_allow_html=True)
        csv_rows.extend(rows)
    return csv_rows


def _render_utilization_tab(scenario: dict[str, Any], results: dict[str, SolverResult]) -> None:
    if not results:
        st.info("Run an allocation to inspect resource workloads against their caps.")
        return
    for solver_name, result in results.items():
        resources, incidents = to_contract_records(scenario)
        metrics = calculate_metrics(resources, incidents, result.assignments)
        assignments_by_resource: dict[str, list[str]] = {resource.id: [] for resource in resources}
        for resource_id, incident_id in result.assignments:
            assignments_by_resource[resource_id].append(incident_id)
        if len(results) > 1:
            st.markdown(f"#### {solver_name} workload")
        for resource in resources:
            count = metrics["assignment_counts"][resource.id]
            cap = resource.max_assignments
            percent = int(round(100 * count / cap)) if cap else 0
            st.markdown(f"**{resource.name}** · `{resource.id}` · {count}/{cap} incidents")
            st.progress(min(percent, 100))
            detail = ", ".join(assignments_by_resource[resource.id]) or "No incident assigned"
            st.caption(f"Capabilities: {', '.join(sorted(resource.skills)) or 'General'} · {detail}")


def _render_benchmark_tab(results: dict[str, SolverResult]) -> None:
    if len(results) < 2:
        st.info("Select **Compare both** and run allocation to benchmark OR-Tools CP-SAT against PuLP.")
        if results:
            name, result = next(iter(results.items()))
            st.caption(f"Current run: {name} · {result.status} · {result.filled_slots}/{result.total_slots} incidents.")
        return
    st.dataframe(
        [
            {
                "Solver": name,
                "Status": result.status,
                "Incidents covered": f"{result.filled_slots}/{result.total_slots}",
                "Preference matches": result.preference_count,
                "Latency (ms)": round(result.elapsed_seconds * 1000, 3),
            }
            for name, result in results.items()
        ],
        width="stretch",
        hide_index=True,
    )
    st.caption("Compare feasibility and score first. Different unit-to-incident assignments can have equal objective value.")


def _render_model_tab() -> None:
    st.markdown("### A small bipartite assignment model")
    st.write(
        "Response resources form one side of a bipartite graph and incidents form the other. "
        "An edge exists only when a unit is available for the incident and has its required capability. "
        "Selecting an edge means dispatching that unit to that incident."
    )
    st.markdown("""
    **Hard constraints**

    - At most one response unit is assigned to each incident.
    - A unit must be available and meet the required skill.
    - A unit cannot exceed its assignment cap.
    - A unit cannot serve two overlapping incident windows. The intervals are half-open: `[start, end)`.
    - Incidents may remain uncovered when no feasible assignment exists.

    **Objective in the current shared solver code**

    `maximize (number of incidents + 1) × covered incidents + eligible preference matches`

    The coefficient makes coverage the first priority; preferences break ties among equally covered allocations. RED/YELLOW/GREEN badges are scenario context for the operations view. **The current solver does not use triage severity as a mathematical weight.** A severity-weighted objective would require a coordinated solver/model update outside this app milestone.
    """)


def main() -> None:
    st.set_page_config(page_title="ReliefOpt", page_icon="🚨", layout="wide")
    st.markdown("""
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px;}
      .hero {padding: 1.35rem 1.6rem; border-radius: 18px; color: #f8fafc;
        background: linear-gradient(120deg,#102a43,#075985 62%,#0f766e); margin-bottom: 1rem;}
      .hero h1 {margin: 0 0 .25rem 0; font-size: 2rem;}
      .hero p {margin: .15rem 0; color: #dbeafe;}
      .pill-row {display:flex; gap:.55rem; flex-wrap:wrap; margin:.4rem 0 1.1rem;}
      .pill {display:inline-block; border-radius:999px; padding:.35rem .75rem;
        background:#e0f2fe; color:#075985; font-size:.78rem; font-weight:700;}
      .pill.alert {background:#fee2e2;color:#991b1b;}
      .pill.ready {background:#dcfce7;color:#166534;}
      .kpi-card {border:1px solid #dbe4ee; border-radius:14px; background:#fff;
        padding:1rem 1.1rem; min-height:120px; box-shadow:0 3px 12px #0f172a0a;}
      .kpi-label {color:#526277;font-size:.82rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;}
      .kpi-value {color:#102a43;font-size:1.55rem;font-weight:750;margin:.35rem 0;}
      .kpi-note,.muted {color:#64748b;font-size:.78rem;}
      .table-wrap {overflow-x:auto;border:1px solid #dbe4ee;border-radius:12px;}
      .dispatch-table {border-collapse:collapse;width:100%;font-size:.86rem;background:white;}
      .dispatch-table th {text-align:left;background:#f1f5f9;color:#334155;padding:.75rem;white-space:nowrap;}
      .dispatch-table td {padding:.72rem;border-top:1px solid #e2e8f0;vertical-align:middle;}
      .triage-badge,.status-badge {display:inline-block;border-radius:999px;padding:.25rem .55rem;font-size:.72rem;font-weight:750;white-space:nowrap;}
      .triage-badge.red {background:#fee2e2;color:#991b1b;}
      .triage-badge.yellow {background:#ffedd5;color:#9a3412;}
      .triage-badge.green {background:#fef9c3;color:#854d0e;}
      .status-badge.dispatched {background:#dcfce7;color:#166534;}
      .status-badge.unattended {background:#fee2e2;color:#991b1b;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        "<div class='hero'><h1>ReliefOpt: Disaster Relief Resource &amp; Task Allocation</h1>"
        "<p>Deterministic Discrete Optimization (OR-Tools CP-SAT &amp; PuLP) for Emergency Dispatch</p></div>",
        unsafe_allow_html=True,
    )

    controls = st.columns([1.25, 1, .85])
    scenario_label = controls[0].selectbox("Response scenario", list(SCENARIO_PATHS))
    solver_choice = controls[1].selectbox("Optimization engine", ["OR-Tools CP-SAT", "PuLP", "Compare both"])
    run_clicked = controls[2].button("Run allocation", type="primary", width="stretch")

    scenario_path = SCENARIO_PATHS[scenario_label]
    try:
        scenario = load_scenario(str(scenario_path))
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        st.error(f"Scenario could not be loaded: {error}")
        return

    shortage_scenario = scenario["scenario_id"] == "limited_staffing"
    pill_style = "alert" if shortage_scenario else "ready"
    status_label = "RESOURCE SHORTAGE SCENARIO" if shortage_scenario else "NORMAL RESPONSE CAPACITY"
    st.markdown(
        f"<div class='pill-row'><span class='pill {pill_style}'>🚨 {status_label}</span>"
        f"<span class='pill'>Vadodara flood response · {len(scenario['volunteers'])} units</span>"
        f"<span class='pill'>{len(scenario['slots'])} incidents</span>"
        "<span class='pill'>Deterministic · local prototype</span></div>",
        unsafe_allow_html=True,
    )
    st.caption(scenario.get("description", ""))

    context = (scenario["scenario_id"], solver_choice)
    if run_clicked:
        st.session_state.pop("last_results", None)
        st.session_state.pop("last_context", None)
        try:
            st.session_state["last_results"] = run_solvers(scenario, solver_choice)
            st.session_state["last_context"] = context
        except (ValidationError, RuntimeError, TypeError, ValueError) as error:
            st.error(f"Allocation could not be completed: {error}")
        except Exception as error:
            st.error(f"{solver_choice} failed ({type(error).__name__}): {error}")

    results = st.session_state.get("last_results", {})
    if st.session_state.get("last_context") != context:
        results = {}

    if results:
        kpis = st.columns(4)
        with kpis[0]:
            _render_kpi("Incidents covered", _format_coverage(results), "Assigned / total incidents")
        with kpis[1]:
            if len(results) == 1:
                result = next(iter(results.values()))
                coverage = result.filled_slots / result.total_slots * 100 if result.total_slots else 0
                value = f"{coverage:.0f}%"
            else:
                percentages = {round(r.filled_slots / r.total_slots * 100) if r.total_slots else 0 for r in results.values()}
                value = f"{next(iter(percentages))}% each" if len(percentages) == 1 else "See benchmark"
            _render_kpi("Coverage", value, "Share of incidents with a unit")
        with kpis[2]:
            _render_kpi("Preference score", _format_preferences(results), "Eligible preferred assignments · not severity-weighted")
        with kpis[3]:
            _render_kpi("Solver latency", _format_latency(results), "Solver time only")
    else:
        st.info("Select a scenario and solver, then run allocation to populate the command center.")

    manifest_tab, utilization_tab, benchmark_tab, model_tab = st.tabs([
        "📋 Dispatch Manifest", "👥 Resource Utilization", "⚖️ Solver Benchmark", "📘 Model & Disaster Context"
    ])
    with manifest_tab:
        csv_rows = _render_dispatch_tab(scenario, results)
        if csv_rows:
            st.download_button(
                "Download Dispatch Manifest (CSV)",
                data=csv_bytes(csv_rows),
                file_name=f"{scenario['scenario_id']}_dispatch_manifest.csv",
                mime="text/csv",
            )
    with utilization_tab:
        _render_utilization_tab(scenario, results)
    with benchmark_tab:
        _render_benchmark_tab(results)
    with model_tab:
        _render_model_tab()


if __name__ == "__main__":
    main()
