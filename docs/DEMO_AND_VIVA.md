# ShiftWise demo and viva guide

This guide supports the project in [PROJECT_BRIEF.md](../PROJECT_BRIEF.md). The brief remains the source of truth for the mathematical model and app requirements. Current local verification with both solver implementations returned 10/10 slots and 3 preference matches for normal staffing, and 9/10 slots and 3 preference matches for limited staffing, leaving `av-setup` uncovered. Assignment identities may vary.

## Short demo flow

Aim for a concise walkthrough that shows both successful staffing and a real shortage. The exact event records will be supplied later by Darshan; this guide does not prescribe final records.

1. **Introduce the use case.** Explain that a campus event has individual positions to staff. Volunteers have skills, availability, assignment caps, and preferences.
2. **Show the normal-staffing scenario.** Select it, choose OR-Tools or PuLP, and run optimization. The verified result is 10/10 slots and 3 preference matches. Point out the roster and assignment counts.
3. **Explain eligibility and the trade-off.** V05 is listed as available for `photo-booth` but lacks `Photo`, so that pair is excluded. V01 prefers `av-demo` but must cover the only-eligible `workshop-checkin` slot to preserve full coverage.
4. **Show limited staffing.** The verified result is 9/10 slots, with `av-setup` uncovered because no AV-qualified volunteer is available for it.
5. **Compare both solvers.** Choose compare mode. Both report the same coverage and preference scores for these scenarios; elapsed times and roster identities may differ.
6. **Show the matching idea.** Describe volunteers on one side of a bipartite graph and slots on the other. Eligible edges connect possible assignments; the solver selects a useful subset.
7. **Finish with the CSV download.** Download the roster and state that the first version is local and uses deterministic optimization.

For a very short presentation, prioritize steps 1, 2, 4, and 5, then explain the graph and objective verbally. Use [demo_script.md](../demo_script.md) for the compact presenter sequence.

## Course-language explanation

### Combinatorics and matching

The possible assignments are represented by a bipartite graph. Volunteer vertices are on one side and individual role-slot vertices are on the other. An edge exists only if the volunteer is available and has the required skill. A selected edge means that volunteer covers that slot. The optimizer searches among subsets of eligible edges.

It is not a plain one-to-one matching because a volunteer can cover several slots. The model adds an assignment cap and prevents the same volunteer from taking overlapping slots. Each slot still accepts at most one volunteer.

### Decision variables

For every eligible pair `(v,s)`, define binary `x(v,s)`. A value of one means volunteer `v` is assigned to slot `s`; zero means they are not. Ineligible pairs have no decision variable, so availability and skill eligibility are built into the model.

### Objective

The model maximizes:

```text
(number of all slots + 1) * number of filled slots
+ number of assigned preferred pairs
```

There can be at most one preference point per filled slot, so preference points are never greater than the total number of slots. The weight `|S| + 1` means gaining one slot always outweighs losing every possible preference point. Therefore the model first maximizes coverage and then uses preferences to choose among equally covered rosters.

### Constraints

- At most one volunteer is selected for each slot.
- A volunteer's assignment count cannot exceed their event cap.
- One volunteer cannot take two slots whose time intervals overlap.
- Only available volunteers with any required skill can be assigned.
- A slot may remain empty, allowing the solver to produce a partial roster when staffing is insufficient.

Availability, skill, overlap, and caps are hard constraints. Preferences are soft priorities represented in the objective, so an assignment may ignore a preference when needed to fill more positions.

## Likely viva questions

### Why model this as a bipartite graph?

There are two distinct sets—volunteers and slots—and possible assignments naturally connect one member of each set. The edges make eligibility explicit and correspond directly to assignment decisions.

### Why use binary variables?

An assignment is either selected or not selected. A binary variable expresses that yes/no choice and lets the model enforce slot, cap, and conflict limits.

### Why is coverage weighted more heavily than preferences?

The preference score can never exceed the number of slots. A coefficient of one more than that count guarantees that one additional filled slot is worth more than any possible preference-score loss. This implements the stated priority exactly.

### Why can the model leave a slot unfilled?

The slot constraint says at most one assignment, not exactly one. The all-zero assignment is feasible, so shortages can be returned as a partial roster instead of making the model fail.

### How are overlapping shifts detected?

Use half-open time intervals `[start, end)`. Two slots overlap when each starts before the other ends: `start1 < end2` and `start2 < end1`. If one ends exactly when another starts, they do not overlap.

### What is the difference between a hard constraint and a preference?

A hard constraint must hold in every returned roster, such as availability or a skill requirement. A preference is a soft objective point. The model may leave a preference unmet to preserve or improve coverage.

### Why do OR-Tools and PuLP sometimes select different volunteers?

They encode the same objective and constraints, but there may be multiple rosters with the same maximum coverage and preference score. Solvers can return different optimal assignments due to search order or tie-breaking. Compare the scores and validity, not exact roster identity.

### What does the app report when no roster can fill everything?

It shows the best feasible assignments, filled and total slots, coverage percentage, preference matches, and the explicit list of uncovered slots. The roster remains useful even when it is incomplete.

### Why use two optimization libraries?

Implementing the same model in OR-Tools CP-SAT and PuLP demonstrates that the mathematical formulation is independent of one library's syntax and makes solver results comparable. PuLP also requires a working backend, which the team verifies in the target environment.

### Does the running app use AI?

No. The application uses deterministic optimization. AI tools may support development or review, but the application itself requires no generative AI service or API key.

## Presentation preparation checklist

- [ ] Both solver paths and the selected PuLP backend work on the presentation machine.
- [ ] The normal scenario fills most or all slots; limited staffing leaves at least one open.
- [ ] The team can explain the shortage from the actual fictional records.
- [ ] The comparison view is ready, and the presenter knows that equal scores can yield different assignments.
- [ ] The CSV download has been tried.
- [ ] Each team member can describe their assigned component without implying there is a project lead.
