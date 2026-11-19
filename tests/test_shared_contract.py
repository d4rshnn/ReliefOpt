import unittest

from shiftwise.helpers import is_eligible, slots_overlap
from shiftwise.metrics import (
    assignment_counts,
    calculate_metrics,
    coverage_percentage,
    preference_matches,
    uncovered_slot_ids,
)
from shiftwise.models import ShiftSlot, Volunteer
from shiftwise.validation import ValidationError, validate_assignments, validate_inputs, validate_scenario


class SharedContractTests(unittest.TestCase):
    def setUp(self):
        self.volunteers = [
            Volunteer("v1", "Asha", ["AV"], ["s1", "s2"], 2, ["s1"]),
            Volunteer("v2", "Ravi", {"Photo"}, {"s2"}, 1, set()),
        ]
        self.slots = [
            ShiftSlot("s1", "Setup", 540, 600, "AV"),
            ShiftSlot("s2", "Photo", 600, 660, None),
        ]

    def test_valid_records_and_collection_normalization(self):
        validate_inputs(self.volunteers, self.slots, require_slots=True)
        self.assertEqual(self.volunteers[0].skills, frozenset({"AV"}))
        self.assertEqual(self.volunteers[0].available_slot_ids, frozenset({"s1", "s2"}))

    def test_json_mapping_scenario_validation(self):
        scenario = {
            "scenario_id": "memory-demo",
            "label": "In-memory demo",
            "volunteers": [{
                "id": "v1", "name": "Asha", "skills": ["AV"],
                "available_slot_ids": ["s1"], "max_assignments": 1,
                "preferred_slot_ids": [],
            }],
            "slots": [{
                "id": "s1", "role": "Setup", "start_time": 540,
                "end_time": 600, "required_skill": "AV",
            }],
        }
        validate_scenario(scenario)

    def test_validation_reports_multiple_actionable_errors(self):
        bad_volunteers = [{
            "id": "v1", "name": "", "skills": ["AV", "AV"],
            "available_slot_ids": ["missing"], "max_assignments": True,
            "preferred_slot_ids": ["missing"],
        }, {
            "id": "v1", "name": "Second", "skills": [],
            "available_slot_ids": [], "max_assignments": -1,
            "preferred_slot_ids": [],
        }]
        bad_slots = [{
            "id": "s1", "role": "", "start_time": 600,
            "end_time": 600, "required_skill": " ",
        }, {
            "id": "s1", "role": "Duplicate", "start_time": 0,
            "end_time": 10, "required_skill": 7,
        }]
        with self.assertRaises(ValidationError) as caught:
            validate_inputs(bad_volunteers, bad_slots)
        message = str(caught.exception)
        for expected in ("Duplicate slot ID", "Duplicate volunteer ID", "unknown slot", "nonnegative integer", "end_time greater", "required_skill"):
            self.assertIn(expected, message)

    def test_missing_fields_and_empty_demo_slots(self):
        with self.assertRaises(ValidationError) as caught:
            validate_inputs([{"id": "v1"}], [], require_slots=True)
        self.assertIn("missing required field", str(caught.exception))
        self.assertIn("At least one slot", str(caught.exception))

    def test_model_rejects_duplicate_or_malformed_collection_values(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            Volunteer("v", "Name", ["AV", "AV"], [], 1, [])
        with self.assertRaisesRegex(ValueError, "nonempty strings"):
            Volunteer("v", "Name", [""], [], 1, [])

    def test_eligibility_uses_availability_and_required_skill(self):
        self.assertTrue(is_eligible(self.volunteers[0], self.slots[0]))
        self.assertFalse(is_eligible(self.volunteers[1], self.slots[0]))
        self.assertTrue(is_eligible(self.volunteers[1], self.slots[1]))
        self.assertFalse(is_eligible(self.volunteers[1], ShiftSlot("s2", "Photo", 600, 660, "AV")))

    def test_half_open_overlap_boundaries(self):
        adjacent = ShiftSlot("s3", "Next", 600, 660, None)
        overlapping = ShiftSlot("s4", "Overlap", 599, 620, None)
        self.assertFalse(slots_overlap(self.slots[0], adjacent))
        self.assertTrue(slots_overlap(self.slots[0], overlapping))
        self.assertTrue(slots_overlap(overlapping, self.slots[0]))

    def test_metrics(self):
        assignments = [("v1", "s1"), ("v2", "s2")]
        self.assertEqual(uncovered_slot_ids(self.slots, assignments), [])
        self.assertEqual(coverage_percentage(2, 2), 100.0)
        self.assertEqual(coverage_percentage(0, 0), 0.0)
        self.assertEqual(preference_matches(self.volunteers, assignments), 1)
        self.assertEqual(assignment_counts(self.volunteers, assignments), {"v1": 1, "v2": 1})
        summary = calculate_metrics(self.volunteers, self.slots, assignments)
        self.assertEqual(summary["filled_slots"], 2)
        self.assertEqual(summary["preference_count"], 1)
        self.assertEqual(summary["uncovered_slot_ids"], [])

    def test_metrics_identify_uncovered_slot_and_zero_assignment_volunteers(self):
        summary = calculate_metrics(self.volunteers, self.slots, [("v1", "s1")])
        self.assertEqual(summary["uncovered_slot_ids"], ["s2"])
        self.assertEqual(summary["assignment_counts"], {"v1": 1, "v2": 0})
        self.assertEqual(summary["coverage_percentage"], 50.0)

    def test_assignment_validation_accepts_valid_roster(self):
        validate_assignments(self.volunteers, self.slots, [("v1", "s1"), ("v2", "s2")])

    def test_assignment_validation_rejects_hard_constraint_violations(self):
        overlapping_slots = [
            ShiftSlot("a", "A", 540, 610, "AV"),
            ShiftSlot("b", "B", 600, 660, "AV"),
        ]
        volunteers = [Volunteer("v1", "Asha", ["AV"], ["a", "b"], 1, [])]
        with self.assertRaises(ValidationError) as caught:
            validate_assignments(volunteers, overlapping_slots, [("v1", "a"), ("v1", "b")])
        self.assertIn("exceeding cap", str(caught.exception))
        self.assertIn("overlapping slots", str(caught.exception))

        with self.assertRaises(ValidationError) as caught:
            validate_assignments(self.volunteers, self.slots, [("v2", "s1")])
        self.assertIn("not eligible", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
