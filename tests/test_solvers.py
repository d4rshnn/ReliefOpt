"""Focused integration tests for ReliefOpt solvers, data, and app adapters."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import app
from shiftwise.helpers import is_eligible
from shiftwise.metrics import assignment_counts, uncovered_slot_ids
from shiftwise.models import ShiftSlot, SolverResult, Volunteer
from shiftwise.solver_ortools import solve as solve_ortools
from shiftwise.solver_pulp import _normalize_status, solve as solve_pulp
from shiftwise.validation import ValidationError, validate_assignments, validate_scenario


ROOT = Path(__file__).resolve().parents[1]
SOLVERS = (solve_ortools, solve_pulp)


def load_scenario(name: str):
    with (ROOT / "data" / f"{name}.json").open(encoding="utf-8") as source:
        scenario = json.load(source)
    validate_scenario(scenario)
    return scenario


class SolverIntegrationTests(unittest.TestCase):
    def test_nonoptimal_incumbent_is_reported_as_feasible(self):
        self.assertEqual(_normalize_status("Not Solved", True), "feasible")
        self.assertEqual(_normalize_status("Infeasible", True), "no_solution")

    def test_both_scenarios_validate_and_have_expected_coverage(self):
        normal = load_scenario("normal_staffing")
        limited = load_scenario("limited_staffing")
        self.assertEqual((len(normal["volunteers"]), len(normal["slots"])), (11, 10))
        self.assertEqual((len(limited["volunteers"]), len(limited["slots"])), (11, 10))

        for solve in SOLVERS:
            with self.subTest(solver=solve.__module__, scenario="normal"):
                volunteers, slots = app.to_contract_records(normal)
                result = solve(volunteers, slots)
                self.assertIsInstance(result, SolverResult)
                self.assertEqual(result.status, "optimal")
                self.assertEqual((result.filled_slots, result.total_slots), (10, 10))
                validate_assignments(volunteers, slots, result.assignments)
                self.assertEqual(result.preference_count, 10)
                validate_assignments(volunteers, slots, result.assignments)

            with self.subTest(solver=solve.__module__, scenario="limited"):
                volunteers, slots = app.to_contract_records(limited)
                result = solve(volunteers, slots)
                self.assertIsInstance(result, SolverResult)
                self.assertEqual(result.status, "optimal")
                self.assertEqual((result.filled_slots, result.total_slots), (9, 10))
                self.assertEqual(result.preference_count, 9)
                self.assertEqual(uncovered_slot_ids(slots, result.assignments), ["rooftop-flood-rescue"])
                validate_assignments(volunteers, slots, result.assignments)

    def test_both_solvers_agree_on_coverage_and_preference_scores(self):
        for name in ("normal_staffing", "limited_staffing"):
            with self.subTest(scenario=name):
                scenario = load_scenario(name)
                volunteers, slots = app.to_contract_records(scenario)
                ortools_result = solve_ortools(volunteers, slots)
                pulp_result = solve_pulp(volunteers, slots)
                self.assertEqual(ortools_result.status, "optimal")
                self.assertEqual(pulp_result.status, "optimal")
                self.assertEqual(ortools_result.filled_slots, pulp_result.filled_slots)
                self.assertEqual(ortools_result.preference_count, pulp_result.preference_count)

    def test_coverage_beats_a_preferred_roster_with_less_coverage(self):
        volunteers = [
            Volunteer("flex", "Flexible", [], ["preferred", "other"], 2, ["preferred"]),
            Volunteer("forced", "Only preferred slot", [], ["preferred"], 1, []),
        ]
        slots = [
            ShiftSlot("preferred", "Preferred role", 600, 660, None),
            ShiftSlot("other", "Other role", 600, 660, None),
        ]
        for solve in SOLVERS:
            with self.subTest(solver=solve.__module__):
                result = solve(volunteers, slots)
                self.assertEqual(result.status, "optimal")
                self.assertEqual(result.filled_slots, 2)
                self.assertEqual(result.preference_count, 0)
                self.assertEqual(set(result.assignments), {("forced", "preferred"), ("flex", "other")})
                validate_assignments(volunteers, slots, result.assignments)

    def test_one_volunteer_cannot_cover_two_overlapping_slots(self):
        volunteers = [Volunteer("only", "Only volunteer", [], ["first", "second"], 2, [])]
        slots = [
            ShiftSlot("first", "First position", 540, 600, None),
            ShiftSlot("second", "Second position", 599, 660, None),
        ]
        for solve in SOLVERS:
            with self.subTest(solver=solve.__module__):
                result = solve(volunteers, slots)
                self.assertEqual(result.status, "optimal")
                self.assertEqual(result.filled_slots, 1)
                validate_assignments(volunteers, slots, result.assignments)

    def test_caps_and_overlap_constraints_are_enforced(self):
        scenario = load_scenario("normal_staffing")
        volunteers, slots = app.to_contract_records(scenario)
        results = [solve(volunteers, slots) for solve in SOLVERS]
        for result in results:
            validate_assignments(volunteers, slots, result.assignments)
            counts = assignment_counts(volunteers, result.assignments)
            by_id = {volunteer.id: volunteer for volunteer in volunteers}
            for volunteer_id, count in counts.items():
                self.assertLessEqual(count, by_id[volunteer_id].max_assignments)
            self.assertEqual(counts["DRONE-SUPPLY-01"], 1)

        # The drone can cover either of two non-overlapping preferred supply
        # jobs, but its cap is one. The cap—not a time conflict—prevents both.
        by_id = {slot.id: slot for slot in slots}
        self.assertEqual(by_id["clean-water-delivery"].end_time, 660)
        self.assertEqual(by_id["food-relief-convoy"].start_time, 720)
        drone = next(unit for unit in volunteers if unit.id == "DRONE-SUPPLY-01")
        self.assertTrue(is_eligible(drone, by_id["clean-water-delivery"]))
        self.assertTrue(is_eligible(drone, by_id["food-relief-convoy"]))
        with self.assertRaisesRegex(ValidationError, "exceeding cap"):
            validate_assignments(
                volunteers,
                slots,
                [("DRONE-SUPPLY-01", "clean-water-delivery"), ("DRONE-SUPPLY-01", "food-relief-convoy")],
            )

    def test_dataset_has_availability_and_skill_exclusions_and_preferences(self):
        scenario = load_scenario("normal_staffing")
        volunteers, slots = app.to_contract_records(scenario)
        volunteers_by_id = {volunteer.id: volunteer for volunteer in volunteers}
        slots_by_id = {slot.id: slot for slot in slots}
        self.assertIn("rooftop-flood-rescue", volunteers_by_id["NDRF-TEAM-01"].available_slot_ids)
        self.assertFalse(is_eligible(volunteers_by_id["NDRF-TEAM-01"], slots_by_id["rooftop-flood-rescue"]))
        self.assertTrue(is_eligible(volunteers_by_id["NDRF-BOAT-01"], slots_by_id["rooftop-flood-rescue"]))
        limited = load_scenario("limited_staffing")
        limited_volunteers, limited_slots = app.to_contract_records(limited)
        limited_by_id = {unit.id: unit for unit in limited_volunteers}
        limited_slot = {slot.id: slot for slot in limited_slots}["rooftop-flood-rescue"]
        self.assertFalse(is_eligible(limited_by_id["NDRF-BOAT-01"], limited_slot))
        self.assertFalse(is_eligible(limited_by_id["NDRF-BOAT-02"], limited_slot))

    def test_invalid_dataset_records_are_rejected(self):
        scenario = load_scenario("normal_staffing")
        cases = []

        duplicate_id = copy.deepcopy(scenario)
        duplicate_id["volunteers"][1]["id"] = duplicate_id["volunteers"][0]["id"]
        cases.append((duplicate_id, "Duplicate volunteer ID"))

        unknown_reference = copy.deepcopy(scenario)
        unknown_reference["volunteers"][0]["available_slot_ids"].append("missing-slot")
        cases.append((unknown_reference, "unknown slot ID"))

        invalid_time = copy.deepcopy(scenario)
        invalid_time["slots"][0]["end_time"] = invalid_time["slots"][0]["start_time"]
        cases.append((invalid_time, "end_time greater"))

        invalid_cap = copy.deepcopy(scenario)
        invalid_cap["volunteers"][0]["max_assignments"] = -1
        cases.append((invalid_cap, "nonnegative integer"))

        for invalid_scenario, expected in cases:
            with self.subTest(expected=expected), self.assertRaises(ValidationError) as caught:
                validate_scenario(invalid_scenario)
            self.assertIn(expected, str(caught.exception))

    def test_app_adapter_and_csv_include_unfilled_slots(self):
        scenario = load_scenario("limited_staffing")
        volunteers, slots = app.to_contract_records(scenario)
        self.assertIsInstance(volunteers[0], Volunteer)
        self.assertIsInstance(slots[0], ShiftSlot)
        results = app.run_solvers(scenario, "Compare both")
        self.assertEqual(set(results), {"OR-Tools CP-SAT", "PuLP"})
        result = results["OR-Tools CP-SAT"]
        rows = app.result_rows(scenario, result, "OR-Tools CP-SAT")
        self.assertEqual(len(rows), 10)
        unfilled = [row for row in rows if row["Dispatch status"] == "UNATTENDED"]
        self.assertEqual([row["Incident"] for row in unfilled], ["rooftop-flood-rescue"])
        csv_text = app.csv_bytes(rows).decode("utf-8")
        self.assertIn("Solver,Triage,Incident,Role,Time,Required capability,Response unit,Resource ID,Dispatch status", csv_text)
        self.assertIn("rooftop-flood-rescue", csv_text)
        self.assertIn("UNATTENDED", csv_text)


if __name__ == "__main__":
    unittest.main()
