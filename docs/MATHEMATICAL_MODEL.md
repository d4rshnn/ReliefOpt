# ReliefOpt: Disaster Relief Resource Allocation
## Mathematical Model & Discrete Optimization Specification

**Author:** Shriyans Bharuka (OR-Tools CP-SAT Implementation Lead)  
**Project:** ReliefOpt / DisasterRelief — Program Development Laboratory (PDL)  
**Evaluator Target:** Discrete Mathematics Faculty  
**Inspiration:** [DisasterRelief](https://github.com/ShriyansBharuka/DisasterRelief) (Refactored into pure, explainable discrete optimization)

---

## 1. Executive Summary & Problem Formulation

In a rapid-onset disaster (e.g., the Vadodara city flood of August 2024), municipal emergency response centers are inundated with simultaneous distress calls across multiple sectors. Available emergency response assets—such as National Disaster Response Force (NDRF) rescue boats, Advanced Life Support (ALS) ambulances, specialized medical vans, drone supply units, and heavy rescue vehicles—are constrained by:
1. **Specialized Capabilities:** A flooded sector requires amphibious rescue boats; severe trauma requires an ALS ambulance; a collapsed building requires heavy extrication equipment.
2. **Operational Shift Capacities:** Responders face physical exhaustion; each unit has a strictly enforced operational capacity cap ($\text{cap}(r)$).
3. **Temporal Conflicts (Overlapping Windows):** A single response unit cannot execute two simultaneous rescue missions in different geographical sectors.
4. **Life-Threatening Scarcity:** When calls exceed total fleet capacity, the system must produce a maximal partial matching and explicitly flag unattended critical incidents for escalation.

Naive dispatch heuristics (**"first-come, first-served"** or **"greedy nearest-first"**) lead to fatal inefficiencies: dispatching an ALS boat to a minor food run leaves stranded rooftop victims to drown minutes later. ReliefOpt solves this globally via **Constrained Bipartite Matching**.

---

## 2. Graph-Theoretic Formulation

The problem is formalized as a bipartite graph $G = (R \cup I, E)$:

### Partitions:
* **$R$ (Left Vertices — Emergency Response Units):**
  $$R = \{r_1, r_2, \dots, r_n\}$$
  Each resource $r \in R$ is characterized by:
  - $\text{capabilities}(r) \subseteq \Sigma$: specialized capabilities (e.g., `{"Boat", "Water_Rescue", "ALS"}`).
  - $\text{windows}(r) \subseteq I$: available operational windows / sectors.
  - $\text{cap}(r) \in \mathbb{Z}_{\ge 0}$: maximum number of incidents the unit may be assigned during the operational cycle.
  - $\text{pref}(r) \subseteq I$: designated primary sector / specialty preference.

* **$I$ (Right Vertices — Emergency Incidents / Distress Tasks):**
  $$I = \{i_1, i_2, \dots, i_m\}$$
  Each incident $i \in I$ is characterized by:
  - $\text{role}(i)$: incident classification (e.g., *"Rooftop Evacuation"*, *"Trauma Patient Transfer"*).
  - $[\text{start}(i), \text{end}(i))$: operational execution time interval in integer minutes after midnight ($0 \le \text{start}(i) < \text{end}(i) \le 1440$).
  - $\text{req\_capability}(i) \in \Sigma \cup \{\text{null}\}$: mandatory equipment/capability required, or $\text{null}$ for general assistance.

### Eligible Edges ($E$):
An edge connects resource $r$ and incident $i$ if and only if unit $r$ possesses the required capability and is operational in that time window:
$$E = \left\{ (r, i) \in R \times I \;\middle|\; i \in \text{windows}(r) \;\land\; (\text{req\_capability}(i) = \text{null} \;\lor\; \text{req\_capability}(i) \in \text{capabilities}(r)) \right\}$$

### Preferred Edges ($P$):
$$P = \left\{ (r, i) \in E \;\middle|\; i \in \text{pref}(r) \right\}$$

> **Graph-Theoretic Principle:** Ineligible edges $(r, i) \notin E$ are eliminated *a priori* before formulating the mathematical program. This eliminates non-viable paths by construction, reducing the search space and ensuring that no uncertified unit is ever dispatched.

---

## 3. Decision Variables

For each eligible edge $(r, i) \in E$, define a binary decision variable:

$$x_{r,i} \in \{0, 1\} \quad \forall (r,i) \in E$$

$$\text{Where: } x_{r,i} = \begin{cases} 
1 & \text{if response unit } r \text{ is dispatched to incident } i \\
0 & \text{otherwise}
\end{cases}$$

---

## 4. Objective Function: Coverage-First Priority

The global objective function maximizes total incidents served while secondarily optimizing sector proximity and unit preferences:

$$\max \quad Z = (|I| + 1) \sum_{(r,i) \in E} x_{r,i} + \sum_{(r,i) \in P} x_{r,i}$$

### Mathematical Proof of Coverage Dominance

**Theorem:** Under objective function $Z$, any allocation that services $k + 1$ incidents strictly outscores any allocation that services $k$ incidents, regardless of how many preferences or proximity points the $k$-incident allocation satisfies.

**Proof:**
1. Let $I_{\text{served}} = \sum_{(r,i) \in E} x_{r,i}$ denote the total incidents served in allocation $\mathcal{A}$.
2. Let $P_{\text{satisfied}} = \sum_{(r,i) \in P} x_{r,i}$ denote the total preferred/priority matches in $\mathcal{A}$.
3. By Constraint 1 (at most one unit per incident), each incident $i \in I$ can receive at most one response unit. Thus:
   $$0 \le P_{\text{satisfied}} \le I_{\text{served}} \le |I|$$
4. Consider two valid candidate allocations $\mathcal{A}_1$ and $\mathcal{A}_2$:
   - Allocation $\mathcal{A}_1$ serves $k + 1$ incidents with $0$ preferences satisfied:
     $$Z(\mathcal{A}_1) = (|I| + 1)(k + 1) + 0 = (|I| + 1)k + |I| + 1$$
   - Allocation $\mathcal{A}_2$ serves $k$ incidents and satisfies the maximum possible preferences (all $k$ assignments are preferred, where $k \le |I|$):
     $$Z(\mathcal{A}_2) = (|I| + 1)k + k \le (|I| + 1)k + |I|$$
5. Subtracting the two objective values:
   $$Z(\mathcal{A}_1) - Z(\mathcal{A}_2) \ge \Big((|I| + 1)k + |I| + 1\Big) - \Big((|I| + 1)k + |I|\Big) = 1 > 0$$
6. Therefore, $Z(\mathcal{A}_1) > Z(\mathcal{A}_2)$ strictly holds. Servicing one additional emergency incident yields an objective gain of $(|I| + 1)$, which strictly exceeds the maximum possible score from all $|I|$ secondary preferences combined. Coverage has absolute mathematical dominance; preferences serve strictly as tie-breakers among rosters of equal maximum coverage. $\blacksquare$

---

## 5. Mathematical Constraints

### Constraint 1: Incident Exclusivity (At Most One Unit Per Incident)
Each incident receives at most one primary emergency response unit:

$$\sum_{r : (r,i) \in E} x_{r,i} \le 1 \quad \forall i \in I$$

*(Note: The inequality $\le 1$ allows partial coverage during catastrophic shortages, ensuring the solver does not terminate with an infeasibility exception when resources are overwhelmed).*

### Constraint 2: Unit Workload Capacity (Fatigue Management)
No emergency response team may be dispatched to more tasks than its designated shift capacity cap:

$$\sum_{i : (r,i) \in E} x_{r,i} \le \text{cap}(r) \quad \forall r \in R$$

### Constraint 3: Temporal Interval Conflict Exclusion (No Simultaneous Deployments)
A response unit cannot be deployed to two overlapping emergency tasks simultaneously. Time intervals are half-open $[start, end)$. Two incidents $i_1$ and $i_2$ overlap if and only if:

$$\text{overlap}(i_1, i_2) \iff \text{start}(i_1) < \text{end}(i_2) \;\land\; \text{start}(i_2) < \text{end}(i_1)$$

For every resource unit $r \in R$ and distinct overlapping incidents $i_1, i_2 \in I$ ($i_1 \ne i_2$) where $(r, i_1), (r, i_2) \in E$:

$$x_{r,i_1} + x_{r,i_2} \le 1$$

*Adjacent Shifts:* If $i_1$ ends at 600 (10:00 AM) and $i_2$ starts at 600 (10:00 AM), then $\text{start}(i_2) < \text{end}(i_1)$ is false. Hence, back-to-back shifts do not conflict and are valid.

---

## 6. CP-SAT Solver Implementation Details

The model is implemented in `shiftwise/solver_ortools.py` using Google OR-Tools CP-SAT:

1. **Boolean Variables:** Instantiated via `model.NewBoolVar(f"x_{r}_{i}")` strictly for $(r,i) \in E$.
2. **Mutual Exclusion:** Enforced via `model.AddAtMostOne` for incident exclusivity and temporal overlaps.
3. **Capacity Caps:** Enforced via linear inequality bounds `model.Add(sum(...) <= cap)`.
4. **Deterministic Reproducibility:** Search parameter `solver.parameters.random_seed = 42` guarantees consistent solution trajectories.
5. **Incumbent Recovery:** If search terminates in state `FEASIBLE`, the incumbent partial matching is safely returned with status `"feasible"`.

---

## 7. Mathematical Tracing on Vadodara Flood Scenario

### Scenario 1: Normal Staffing (Full City Response)
* **Parameters:** $|I| = 10$ incidents, $|R| = 11$ response units.
* **Coverage Weight:** $|I| + 1 = 11$.
* **Optimal Allocation Outcome:**
  - Status: `optimal`
  - Served Incidents: $10 / 10$ (100% coverage)
  - Preferred Matches: $4$
  - Objective Value: $11 \times 10 + 4 = 114$
* **Preference Sacrifice Case Study:**
  - Unit `V01` (NDRF Inflatable Boat 1) prefers `av-demo` (`incident-water-rescue`), but is the **only** unit capable of covering `workshop-checkin` (`incident-shallow-evac`).
  - Unit `V02` (NDRF Inflatable Boat 2) can cover `incident-water-rescue`, but cannot cover `incident-shallow-evac`.
  - Both incidents overlap (660–720 min).
  - *Option A (Greedy/Preference):* Assign `V01` to its preferred `incident-water-rescue`. Result: 9 covered, $\le 5$ preferences $\implies Z \le 104$.
  - *Option B (Coverage-First Optimization):* Assign `V02` to `incident-water-rescue` and `V01` to `incident-shallow-evac`. Result: 10 covered, 4 preferences $\implies Z = 114$.
  - **Result:** The optimizer selects Option B ($114 > 104$), deliberately sacrificing a preference to ensure no distress call is left unserved.

### Scenario 2: Limited Staffing (Severe Flood Inundation)
* **Parameters:** $|I| = 10$ incidents, $|R| = 11$ units.
* **Scarcity Condition:** Flood access completely isolates the `av-setup` (`rooftop-flood-evacuation`) site. No boat-qualified unit is available in that window.
* **Optimal Allocation Outcome:**
  - Status: `optimal`
  - Served Incidents: $9 / 10$ (90% coverage)
  - Unattended Incident: `rooftop-flood-evacuation` explicitly flagged as uncovered.
  - Objective Value: $11 \times 9 + 4 = 103$.
  - **Significance:** Proves the model operates gracefully under extreme shortages without infeasibility crashes.
