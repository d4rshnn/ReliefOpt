# ReliefOpt: Disaster Relief Resource & Task Allocation

ReliefOpt is a local, deterministic Streamlit teaching prototype for assigning response units to fictional flood-response incidents in Vadodara. A coordinator chooses a staffing scenario and optimization engine, runs an allocation, reviews the dispatch manifest and any unattended incident, and can download the manifest as CSV.

The project demonstrates combinatorics, bipartite matching, and constrained optimization. It creates a graph between response resources and incidents, removes pairs that fail skill or availability requirements, and chooses a valid subset of the remaining pairs. OR-Tools CP-SAT and PuLP implement the same coverage-first model. This is a classroom prototype, not an operational emergency dispatch system.

## What the app does

- Select the normal response-capacity or limited-staffing scenario.
- Run OR-Tools CP-SAT, PuLP, or both for comparison.
- Show incident triage labels, dispatch assignments, and unattended incidents.
- Show incident coverage, coverage percentage, eligible preference matches, and solver latency.
- Show response-unit workload against each unit’s assignment cap.
- Compare solver status, coverage, preference score, and elapsed time.
- Export the dispatch manifest, including unattended incidents, to CSV.
- Validate scenario data and check assignment eligibility and constraints.

The RED, YELLOW, and GREEN triage labels provide incident context in the interface. **Severity is not an optimization input.** The model maximizes

```text
(number of incidents + 1) × covered incidents + eligible preference matches
```

Coverage therefore has strict priority over preferences; preferences distinguish allocations with equal coverage. See [docs/MATHEMATICAL_MODEL.md](docs/MATHEMATICAL_MODEL.md) and [data/README.md](data/README.md). Some planning material still contains older ShiftWise descriptions and an outdated claim that triage severity affects the objective; the implemented contract, solvers, and dataset notes use the coverage-plus-preferences objective described here.

## Scenarios and verified results

Each fictional scenario contains **11 response resources and 10 incidents**. The normal scenario covers all ten incidents. Limited staffing removes both boat units’ availability for `rooftop-flood-rescue`; no other unit has the required `Boat` skill, so the incident has no eligible resource and remains unattended.

Both configured solvers were run locally against the current records:

| Scenario | OR-Tools CP-SAT | PuLP | Unattended incident |
| --- | --- | --- | --- |
| Normal response capacity | Optimal, 10/10 covered, 10 preference matches | Optimal, 10/10 covered, 10 preference matches | None |
| Limited staffing | Optimal, 9/10 covered, 9 preference matches | Optimal, 9/10 covered, 9 preference matches | `rooftop-flood-rescue` |

Different resource-to-incident assignments can be equally optimal, so compare status and scores rather than expecting identical rosters. Preference matches are not triage points.

## Requirements and PuLP backend

The verified local setup used **Python 3.14.4** and the pinned dependencies in `requirements.txt`: Streamlit 1.67.0, OR-Tools 9.15.6755, PuLP 3.3.2, and `highspy` 1.16.0. The PuLP implementation is a modeling interface; it selects the separately installed **HiGHS** engine through `highspy` when available. The current local run confirmed the selected backend was HiGHS. `requirements.txt` includes `highspy`, so no separate backend installation command is needed after installing project requirements.

## Install and run on Windows PowerShell

Run these commands from the repository root. They create a project-local `.venv` and install the pinned dependencies there.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit serves the app locally and normally opens the default browser at `http://localhost:8501`. If a browser does not open automatically, visit that address. Stop the server by pressing **Ctrl+C** in the PowerShell terminal.

If PowerShell does not allow environment activation, use the environment’s Python directly:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Install and run on macOS/Linux

Python 3.14.4 is the version verified by the project; other Python versions have not been verified here.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically. Stop the server with **Ctrl+C** in the terminal.

## Run the tests

The repository’s tests use Python’s built-in `unittest` framework; pytest is not required by `requirements.txt`. With the project environment active, run:

```powershell
python -m unittest discover -s tests -v
```

Or use the project interpreter without activation:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The current verification ran 20 tests successfully. They cover shared data validation and metrics, eligibility and overlap, scenario outcomes, both solver implementations, constraints, app adapter behavior, and CSV output.

## Troubleshooting

- **`py -3.14` is not recognized:** Install Python 3.14 and enable the Python launcher, or use an installed compatible interpreter to create `.venv`; that alternative has not been verified for this project.
- **`streamlit` or a solver import is missing:** Confirm the project environment is active, then run `python -m pip install -r requirements.txt` from the repository root using that same interpreter.
- **PuLP reports no available backend:** Check that `highspy` installed in the active environment with `python -m pip show highspy`. Re-run the requirements install in the same environment. The app reports backend errors rather than treating them as a successful allocation.
- **The browser page is unavailable:** Confirm the Streamlit process is still running in the terminal and use the local address it prints; port 8501 may already be occupied.
- **An incident is unattended in limited staffing:** This is the intended shortage demonstration, not a solver crash. The limited scenario has no eligible Boat unit for `rooftop-flood-rescue`.

## Data contract and project layout

Resource records contain `id`, `name`, `skills`, `available_slot_ids`, `max_assignments`, and `preferred_slot_ids`. Incident records contain `id`, `role`, `start_time`, `end_time`, and `required_skill`. Times are integer minutes after midnight and use half-open intervals `[start_time, end_time)`. The JSON `incident_triage` map is display metadata and is not passed into the solver objective.

- `app.py` — Streamlit command center and integration.
- `data/` — Darshan-authored synthetic scenarios and their notes.
- `shiftwise/` — shared data models, validation, eligibility/overlap helpers, metrics, and OR-Tools/PuLP solvers.
- `tests/` — `unittest` checks for shared contracts, data, solvers, and app adapters.
- `docs/` — project planning and mathematical/demo documentation; consult current code and data notes where older documents still describe ShiftWise.

## Scope and limitations

ReliefOpt uses small, fictional, preconfigured scenarios and a single response period. It models each incident as needing at most one assigned unit, a unit’s maximum assignment count, availability, required skills, and overlapping time windows. It does not model severity in the objective, routing or travel time, geographic distance, changing conditions, multiple units required for one incident, field communications, live data, user accounts, persistent storage, or online deployment. These are not current features. Any extension to the mathematical contract would need coordinated changes to shared models, validation, both solvers, app, tests, and documentation.

## Contributors

These roles follow the current implementation plan and repository structure. Direct profile URLs were not available in the repository, so each name links to its own contribution detail below rather than to an unverified external profile.

| Contributor | Project contribution |
| --- | --- |
| [Darshan](#darshan) | Synthetic disaster scenarios, dataset notes, Streamlit app, and app integration |
| [Shriansh](#shriansh) | OR-Tools CP-SAT implementation and mathematical model documentation |
| [Atharva](#atharva) | PuLP implementation of the shared optimization model |
| [Manas](#manas) | Shared data structures, validation, common helpers, metrics, and tests/demo support |

### Darshan

Owns authorship of the synthetic normal and limited scenarios and their dataset notes, as well as the Streamlit operations interface and integration.

### Shriansh

Owns the OR-Tools CP-SAT solver implementation and the formal mathematical model documentation.

### Atharva

Owns the PuLP implementation of the same model and shared solver interface.

### Manas

Owns the shared data structures, validation, eligibility/overlap helpers, metrics, and shared-contract test/demo support described by the implementation plan.
