# ShiftWise: Volunteer Shift Scheduler

ShiftWise is a local Streamlit prototype for assigning volunteers to individual event positions. It demonstrates **combinatorics, bipartite matching, and constraints** by modeling eligible volunteer-to-slot pairs and selecting a coverage-first roster with OR-Tools CP-SAT or PuLP. The app is deterministic and does not call a generative AI service.

## Features

- Normal-staffing and limited-staffing Campus Tech Fest scenarios.
- OR-Tools, PuLP, and compare-both solver choices.
- Roster with slot, role, time, required skill, and assigned volunteer.
- Coverage count and percentage, preference matches, per-volunteer assignment counts, and uncovered positions.
- Comparison of status, coverage, preference count, and elapsed solver time.
- CSV download of the displayed roster, including unfilled positions.
- Shared record validation and post-solve checks for eligibility, caps, unique slot assignments, and time conflicts.

The volunteer and slot sets form a bipartite graph. A binary variable represents each eligible pair: the volunteer must be available and have the required skill, if any. The model enforces at most one volunteer per slot, assignment caps, and half-open time conflicts. It maximizes `(number of slots + 1) × filled slots + preference matches`, so no possible preference gain can outweigh an additional filled slot. See [docs/MATHEMATICAL_MODEL.md](docs/MATHEMATICAL_MODEL.md) for the derivation.

## Python and dependencies

The setup below was installed and verified on Windows with **Python 3.14.4**. `requirements.txt` pins the versions used for that verification:

- Streamlit 1.67.0
- OR-Tools 9.15.6755 (CP-SAT)
- PuLP 3.3.2
- HiGHS Python backend `highspy` 1.16.0

PuLP is a modeling library, so the configured HiGHS backend is installed separately through `highspy`. The team verified that PuLP selected HiGHS and solved the project fixtures. CBC is not required by this setup.

## Install and run on Windows PowerShell

Run these commands from the repository root. The virtual environment and packages stay inside `.venv`; `.gitignore` excludes it.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit serves the app locally, normally at `http://localhost:8501`, and opens the default browser. If it does not open automatically, visit that address. Stop the server with **Ctrl+C** in the PowerShell window.

If PowerShell activation is restricted, use the virtual environment interpreter directly instead:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Install and run on macOS/Linux

Python 3.14 is the version verified for this repository; other versions may work but have not been checked here.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open `http://localhost:8501` if the browser does not open automatically. Stop the server with **Ctrl+C**.

## Use the app

1. Select **Normal staffing** to see the full-coverage scenario, or **Limited staffing** to see a deliberate AV setup shortage.
2. Choose **OR-Tools**, **PuLP**, or **Compare both**, then click **Run optimization**.
3. Review filled/total slots, coverage percentage, preference matches, assignment counts, and the uncovered-slot list. Unfilled positions are expected in limited staffing.
4. In compare mode, compare solver status and scores. The volunteer identities may differ when multiple rosters achieve the same objective.
5. Click **Download roster as CSV** to export the displayed roster. In compare mode the CSV includes rows for both solver rosters.

The current synthetic scenarios each contain 11 fictional volunteers and 10 slots. On the verified local environment, both solvers returned **10/10 filled and 3 preference matches** for normal staffing, and **9/10 filled and 3 preference matches** for limited staffing, leaving `av-setup` uncovered. Those counts are checked in the test suite; assignment identity is not required to match.

## Run the tests

With the project environment active:

```powershell
python -m unittest discover -s tests -v
```

Or without activation:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover scenario validation, invalid records, eligibility, half-open overlap, caps, coverage-first preferences, both solver result contracts and score agreement, limited staffing, and app record/CSV handling.

## Project files

- `app.py`: Streamlit app and solver integration.
- `data/`: Darshan-authored synthetic scenarios and dataset notes.
- `shiftwise/`: shared models, validation, eligibility/overlap helpers, metrics, and solvers.
- `tests/`: shared-contract and end-to-end solver/data/app-adapter tests.
- `docs/`: dataset specification, mathematical model, and demo/viva guidance.

## Scope and limitations

This is a local course prototype with fictional records and bundled scenarios. Custom uploads, accounts, databases, online deployment, notifications, and advanced styling are out of scope for the MVP. The committed requirements declare all solver dependencies, including HiGHS; the app reports solver import/backend errors instead of presenting them as successful rosters.
