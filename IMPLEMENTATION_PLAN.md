# ShiftWise implementation plan

This plan records the ownership and integration workflow for the project defined in [PROJECT_BRIEF.md](PROJECT_BRIEF.md), which remains the source of truth for scope, model, and result behavior. The repository now contains the shared layer, both solver modules, dataset, and app; use this plan to coordinate future changes.

## Suggested repository layout

```text
shiftwise-volunteer-scheduler/
├── app.py                         # Streamlit UI and integration (Darshan)
├── data/                          # Synthetic scenario records (Darshan)
│   ├── normal_staffing.json
│   └── limited_staffing.json
├── shiftwise/
│   ├── __init__.py
│   ├── models.py                   # Shared types / data structures (Manas)
│   ├── validation.py              # Input validation (Manas)
│   ├── helpers.py                 # Eligibility and overlap helpers (Manas)
│   ├── metrics.py                 # Result metrics / checks (Manas)
│   ├── solver_ortools.py          # CP-SAT solver (Shriansh)
│   ├── solver_pulp.py             # PuLP solver (Atharva)
│   └── API.md                     # Shared Python contract
├── docs/
│   ├── DATASET_SPEC.md
│   ├── DEMO_AND_VIVA.md
│   └── MATHEMATICAL_MODEL.md       # Shriansh's fuller explanation, if needed
├── demo_script.md                 # Demo sequence / cues (Manas)
├── tests/
│   ├── test_shared_contract.py
│   └── test_solvers.py
├── requirements.txt               # Coordinated dependency list
└── README.md                      # Coordinated setup and run instructions
```

This is a suggested layout, not a requirement to create all files in this planning phase. Keep the eventual application and solver code small. The team may adjust paths together if the repository's conventions evolve.

## Frozen interface and parallel work

The Python-level contract in the [brief](PROJECT_BRIEF.md#solver-requirements-and-shared-contract) is the shared interface. Freeze it first: minute-after-midnight integer times, half-open interval overlap, the `Volunteer`, `ShiftSlot`, and `SolverResult` fields, `solve(volunteers, slots)`, and normalized status values. Manas records these types in `shiftwise/models.py` and helper signatures in a brief API note. After that interface is agreed, all four members can work on separate owned files in parallel against it; no one waits for the dataset or for another member's finished solver.

For local parallel work, members can use the agreed contract in this brief or a tiny temporary in-memory fixture in their own uncommitted work. Do not check synthetic scenario records into the shared dataset path except through Darshan's ownership. No Git branch, stage, commit, or push is a prerequisite for starting a separate file task.

If an implementation reveals that the contract must change, the person proposing the change announces the field or behavior and reason to the team. The team agrees on the change, updates this brief/API note, and then updates affected implementations. Do not silently change a shared field or make one person the approval bottleneck.

## Ownership and member task checklists

There are exactly four members and no project lead.

### Darshan — dataset and Streamlit app

- [ ] Design, author, and document all actual synthetic records and assumptions for both scenarios.
- [ ] Manually check that the data demonstrates every case in [DATASET_SPEC.md](docs/DATASET_SPEC.md).
- [ ] Build the Streamlit selectors, run action, roster/uncovered views, metrics, solver comparison, and CSV download.
- [ ] Integrate solver results against the frozen contract and show partial results clearly.
- [ ] Keep app/data file work isolated so other members can begin against the frozen contract.

Darshan owns dataset design and creation only for the dataset. Darshan is not project lead.

### Shriansh — OR-Tools and mathematical explanation

- [ ] Implement the CP-SAT module against the frozen `solve(volunteers, slots)` interface.
- [ ] Implement eligibility variables, all hard constraints, and the coverage-first preference objective.
- [ ] Return normalized status, assignment pairs, counts, and elapsed seconds.
- [ ] Explain the model and objective in `docs/MATHEMATICAL_MODEL.md` or the agreed equivalent.
- [ ] Use the shared contract or a private temporary fixture while Darshan authors the dataset.

### Atharva — PuLP solver

- [ ] Implement the same mathematical model in a separate PuLP module against the frozen interface.
- [ ] Confirm the chosen PuLP backend is installed and callable in the target environment.
- [ ] Return the same result fields and normalized status semantics as the OR-Tools implementation.
- [ ] Use the shared contract or a private temporary fixture; do not wait for the final dataset.

### Manas — shared structures, validation, helpers, metrics, and demo script

- [ ] Implement shared model types and agreed field representations.
- [ ] Validate unique IDs, known slot references, valid time ranges, nonnegative assignment limits, and internally consistent records.
- [ ] Provide common eligibility and half-open overlap helpers.
- [ ] Provide result metrics or checks used by the app/demo, including per-volunteer assignment counts and uncovered slots.
- [ ] Write the concise demo script using the agreed scenarios and interface.
- [ ] Keep shared code independent of actual synthetic record authorship; Darshan's completed records are not a prerequisite.

## Work order and integration sequence

1. **Freeze the interface.** Agree to the contract and helper semantics in the brief/API note. This is the only coordination dependency before parallel work starts.
2. **Work in parallel.** Darshan builds the data and app; Shriansh and Atharva build separate solvers; Manas builds types, validation, helpers, metrics, and demo cues. Each person uses the contract and a local temporary fixture as needed.
3. **Integrate shared structures.** Solver owners adapt to Manas's final field names and helper signatures after the contract is frozen. Interface changes use the announce-agree-document process above.
4. **Integrate each solver independently.** Run both solvers against a small valid fixture and then Darshan's normal and limited scenarios. Validate all returned pairs and constraints.
5. **Integrate the app.** Connect the selectors and button to one or both `solve` functions; confirm displayed metrics use the returned result and scenario data.
6. **Check the environment.** Install dependencies from the coordinated `requirements.txt`, verify OR-Tools CP-SAT availability, and verify PuLP can invoke its selected backend.
7. **Rehearse the demo.** Follow [docs/DEMO_AND_VIVA.md](docs/DEMO_AND_VIVA.md), including CSV download and a clear limited-staffing shortage.

README and `requirements.txt` are shared files. Propose edits in the team channel, agree on the change, then have the relevant owners update them. The README should provide environment setup, app launch, and backend notes; the dependency file should pin or bound the libraries the team actually verifies.

## Manual verification checklist

- [ ] Input validation catches duplicate volunteer or slot IDs, unknown slot references, invalid times, negative caps, and malformed scenario data with actionable messages.
- [ ] Eligibility excludes unavailable volunteers and volunteers missing a required skill; slots with no special skill can accept any otherwise available volunteer.
- [ ] Every returned assignment references a known eligible pair.
- [ ] A volunteer has no more assignments than their cap and no pair of overlapping assigned slots.
- [ ] A slot is assigned at most once; an impossible slot remains explicitly unfilled.
- [ ] A preferred slot is counted only when its preferred volunteer is actually assigned there.
- [ ] Coverage has priority over preference points; verify the constructed preference trade-off scenario.
- [ ] Both solvers receive the same scenario and report filled count, total count, and preference count. If several optima exist, compare objective scores rather than requiring identical assignments.
- [ ] Normal staffing fills most or all slots; limited staffing leaves at least one uncovered slot.
- [ ] Streamlit displays roster, shortage, coverage, preference and per-volunteer metrics, solver comparison, and a usable CSV download.
- [ ] PuLP's configured backend solves an actual model in the target presentation environment.

## Deadline priorities and stretch work

### MVP priority order

1. Freeze the contract and complete both synthetic scenarios.
2. Get both equivalent solvers working and validate hard constraints.
3. Connect the Streamlit workflow and display uncovered positions and scores.
4. Confirm the PuLP backend and rehearse the course explanation.
5. Finish CSV export and concise run/demo instructions.

If time becomes tight, preserve the deterministic model, both working solver paths, normal and shortage scenarios, validation, and a clear demo. Keep styling simple. After the MVP works, consider custom uploads, account management, a database, deployment, notifications, or elaborate visual styling.

## Dependencies and environment notes

The verified local environment is Windows with Python 3.14.4, Streamlit 1.67.0, OR-Tools 9.15.6755, PuLP 3.3.2, and the HiGHS Python backend `highspy` 1.16.0. These versions are pinned in `requirements.txt`; `.venv/` is the project-local environment and is ignored by Git. OR-Tools CP-SAT is supplied through the OR-Tools package. PuLP uses HiGHS via `highspy`; the team verified an actual optimization rather than relying on an import check. Re-run the test suite and local app smoke check after dependency changes.

The application runs locally with no AI credentials or online service requirement. Any optional package setup that requires downloads should be done early enough to catch platform or network issues.
