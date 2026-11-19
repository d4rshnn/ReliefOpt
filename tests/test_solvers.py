"""Focused integration tests for the ShiftWise solvers, data, and app adapters."""

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
                assigned = dict((slot_id, volunteer_id) for volunteer_id, slot_id in result.assignments)
                self.assertEqual(assigned["workshop-checkin"], "V01")
                self.assertNotEqual(assigned.get("av-demo"), "V01")
                self.assertEqual(assignment_counts(volunteers, result.assignments)["V03"], 1)

            with self.subTest(solver=solve.__module__, scenario="limited"):
                volunteers, slots = app.to_contract_records(limited)
                result = solve(volunteers, slots)
                self.assertIsInstance(result, SolverResult)
                self.assertEqual(result.status, "optimal")
                self.assertEqual((result.filled_slots, result.total_slots), (9, 10))
                self.assertEqual(uncovered_slot_ids(slots, result.assignments), ["av-setup"])
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
            self.assertEqual(counts["V03"], 1)

        # V03's preferred positions are non-overlapping, so the cap—not a time
        # conflict—prevents it from covering both in one roster.
        by_id = {slot.id: slot for slot in slots}
        self.assertEqual(by_id["registration-1"].end_time, 600)
        self.assertEqual(by_id["info-desk"].start_time, 720)
        v03 = next(volunteer for volunteer in volunteers if volunteer.id == "V03")
        self.assertTrue(is_eligible(v03, by_id["registration-1"]))
        self.assertTrue(is_eligible(v03, by_id["info-desk"]))
        with self.assertRaisesRegex(ValidationError, "exceeding cap"):
            validate_assignments(
                volunteers,
                slots,
                [("V03", "registration-1"), ("V03", "info-desk")],
            )

    def test_dataset_has_availability_and_skill_exclusions_and_preferences(self):
        scenario = load_scenario("normal_staffing")
        volunteers, slots = app.to_contract_records(scenario)
        volunteers_by_id = {volunteer.id: volunteer for volunteer in volunteers}
        slots_by_id = {slot.id: slot for slot in slots}
        self.assertFalse(is_eligible(volunteers_by_id["V04"], slots_by_id["registration-2"]))
        self.assertIn("photo-booth", volunteers_by_id["V05"].available_slot_ids)
        self.assertFalse(is_eligible(volunteers_by_id["V05"], slots_by_id["photo-booth"]))
        self.assertTrue(is_eligible(volunteers_by_id["V07"], slots_by_id["photo-booth"]))

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
        self.assertEqual(set(results), {"OR-Tools", "PuLP"})
        result = results["OR-Tools"]
        rows = app.result_rows(scenario, result, "OR-Tools")
        self.assertEqual(len(rows), 10)
        unfilled = [row for row in rows if row["Volunteer"] == "Unfilled"]
        self.assertEqual([row["Slot"] for row in unfilled], ["av-setup"])
        csv_text = app.csv_bytes(rows).decode("utf-8")
        self.assertIn("Solver,Slot,Role,Time,Required skill,Volunteer,Volunteer ID", csv_text)
        self.assertIn("av-setup", csv_text)
        self.assertIn("Unfilled", csv_text)


if __name__ == "__main__":
    unittest.main()
