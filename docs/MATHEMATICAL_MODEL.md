# ShiftWise mathematical model

This explanation accompanies the source-of-truth requirements in [PROJECT_BRIEF.md](../PROJECT_BRIEF.md). The actual fictional records are kept in `data/normal_staffing.json` and `data/limited_staffing.json`; this document reports verified score summaries without duplicating those records.

## Bipartite assignment graph

Let `V` be the volunteer set and `S` the set of individual role slots. Represent volunteers as vertices on one side of a bipartite graph and slots as vertices on the other. Include edge `(v,s)` only when volunteer `v` is available for slot `s` and has the required skill, if any. The solver selects a subset of eligible edges. Each slot can receive at most one selected edge; a volunteer can receive several non-overlapping edges up to their assignment cap. This is a constrained assignment model based on bipartite matching, rather than a plain one-to-one matching.

## Decision variables and objective

For each eligible pair `(v,s)`, define a binary variable `x(v,s)`:

- `x(v,s) = 1` means volunteer `v` is assigned to slot `s`.
- `x(v,s) = 0` means that edge is not selected.

Let `P` be the eligible pairs where the slot is in the volunteer's preference set. The model maximizes:

```text
(|S| + 1) * sum(x(v,s) for eligible pairs)
+ sum(x(v,s) for preferred eligible pairs)
```

Because each slot is assigned at most once, preference matches are at most `|S|`. Gaining one filled slot adds `|S| + 1`, which exceeds the maximum possible loss of `|S|` preference matches. Thus coverage always has priority, and preferences choose between rosters with equal coverage.

For a slot `s`, the coefficient on each eligible assignment variable is `|S| + 1`, plus one more when that volunteer prefers `s`. The solver implementations use this equivalent linear objective.

## Constraints

For each slot `s`:

```text
sum(x(v,s) for eligible volunteers v) <= 1
```

For each volunteer `v`:

```text
sum(x(v,s) for eligible slots s) <= max_assignments(v)
```

For any volunteer and overlapping slot pair `s1`, `s2` where both variables exist:

```text
x(v,s1) + x(v,s2) <= 1
```

Slots use integer minutes after midnight and half-open intervals `[start_time, end_time)`. They overlap when `start1 < end2 and start2 < end1`; back-to-back slots do not overlap. Eligibility variables are created only for pairs satisfying both availability and skill requirements. The slot constraint is an upper bound, so the zero-assignment solution is allowed and an understaffed scenario returns a partial roster.

Availability, required skills, assignment caps, and overlaps are hard constraints. Preferences are soft objective points. The normalized status values are `optimal`, `feasible`, and `no_solution`; if a solver returns a feasible incumbent without proving optimality, the app can still display that roster.

## Shared implementation contract

The data structures live in `shiftwise.models`; validation, eligibility/conflict helpers, and metrics are in their corresponding `shiftwise` modules. Both `shiftwise.solver_ortools.solve(volunteers, slots)` and `shiftwise.solver_pulp.solve(volunteers, slots)` return the shared `SolverResult`. The app validates scenario input before solving and validates every assignment before display or CSV export.

## Verified scenario summaries

On the local Windows environment with Python 3.14.4, OR-Tools CP-SAT and PuLP with HiGHS both returned `optimal` for both bundled scenarios:

| Scenario | OR-Tools | PuLP / HiGHS | Verified vacancy |
|---|---:|---:|---|
| Normal staffing | 10/10 filled; 3 preferences | 10/10 filled; 3 preferences | None |
| Limited staffing | 9/10 filled; 3 preferences | 9/10 filled; 3 preferences | `av-setup` |

The exact volunteer-to-slot assignments are not required to match. The scenario files remain the authoritative source for all record details.
