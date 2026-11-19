# Synthetic scenario notes

Darshan alone authored the fictional Campus Tech Fest records in the two JSON files in this directory. Each scenario has 11 volunteers and 10 individual role slots. The JSON files are the source of truth for actual records; this note describes the demonstrations without copying the full roster.

## Scenario intent

- `normal_staffing.json` has a feasible roster covering all 10 positions. Its AV availability permits the setup and demo roles to be staffed by different volunteers.
- `limited_staffing.json` removes all availability for the AV setup role from AV-qualified volunteers. The `av-setup` slot therefore has no eligible volunteer and must remain uncovered; `av-demo` remains staffable.

## Model demonstrations in the records

- **Availability exclusion:** V04 is available for `registration-1` but not `registration-2`.
- **Skill exclusion:** V05 lists `photo-booth` in availability but does not have the required `Photo` skill. V07 and V11 have the skill and are available for that slot.
- **Satisfied preference:** V03 prefers `registration-1`, V06 prefers `cleanup`, and V07 prefers `photo-booth`; these can be assigned in a full-coverage roster.
- **Preference sacrificed for coverage:** V01 prefers `av-demo` and is the only volunteer available for `workshop-checkin`. The slots overlap. Assigning V02 to `av-demo` and V01 to check-in fills both; assigning V01 to the preferred demo slot leaves check-in unfilled.
- **Overlap:** the data has concurrent registration and help-desk positions, plus `av-demo` and `workshop-checkin` at the same time. A volunteer cannot be assigned to two overlapping positions.
- **Binding assignment cap:** V03 has a cap of one and is available for `registration-1` and `info-desk`. Those time intervals do not overlap, so the cap itself prevents V03 from taking both. V03 prefers both positions; it can receive at most one of those preference matches. Other available volunteers can cover whichever slot V03 does not take.
- **Unavoidable shortage:** in limited staffing, no AV-qualified volunteer is available for `av-setup`, so that position cannot be filled.
- **Invalid-input examples:** keep malformed samples out of the runnable scenarios. The shared validator should reject duplicate IDs, unknown availability/preference references, nonpositive slot durations, negative caps, and invalid required-skill values.

## Manual normal-staffing feasibility trace

One full-coverage assignment is:

| Slot | Volunteer ID |
|---|---|
| `registration-1` | V03 |
| `registration-2` | V05 |
| `helpdesk-1` | V11 |
| `helpdesk-2` | V08 |
| `av-setup` | V10 |
| `av-demo` | V02 |
| `workshop-checkin` | V01 |
| `info-desk` | V09 |
| `cleanup` | V06 |
| `photo-booth` | V07 |

This is a feasibility witness, not a promise that either solver will return the identical roster. It respects all listed skills, availability, caps, and overlaps, and it satisfies three listed preferences. Actual solver outcomes should be described only after running the app.

The preference trade-off is forced by eligibility: V01 is the sole candidate for check-in and cannot cover check-in and demo simultaneously. A full-coverage roster therefore leaves V01's demo preference unmet. The V03 cap is independently demonstrable with the non-overlapping `registration-1` and `info-desk` slots; the two registration positions overlap, so they are not the cap example.

## Verified solver outcomes

Using the project-local dependencies on Windows/Python 3.14.4, both implementations returned `optimal` for both scenarios. Each returned 10/10 slots and 3 preference matches for normal staffing; each returned 9/10 and 3 preference matches for limited staffing, with `av-setup` uncovered. The exact assignment lists can differ between solvers and are not part of the expected result.
