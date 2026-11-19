# ShiftWise Mathematical Model and Optimization Specification

**Author:** Shriyans Bharuka (OR-Tools CP-SAT Implementation Lead)  
**Project:** ShiftWise Volunteer Shift Scheduler — Program Development Laboratory (PDL)

---

## 1. Executive Summary and Problem Overview

The ShiftWise scheduler solves a **constrained bipartite matching and resource allocation problem** for event staffing. Given a set of volunteers with individual availability, skills, assignment capacities, and preferences, and a set of shift slots defined by roles, times, and skill prerequisites, the model constructs an optimal roster that:

1. **Strictly satisfies all hard constraints:** availability, required skills, slot exclusivity, volunteer workload caps, and time conflict (overlap) prevention.
2. **Prioritizes total shift coverage above all else:** filling an open position always takes precedence over satisfying any number of volunteer preferences.
3. **Maximizes preference satisfaction secondarily:** breaking ties among equally optimal full- or partial-coverage rosters to assign volunteers to roles they prefer.
4. **Gracefully degrades under staff shortages:** producing a feasible incumbent partial roster and identifying unfilled positions rather than failing.

---

## 2. Formal Graph-Theoretic Formulation

The problem is modeled on an undirected bipartite graph $G = (V \cup S, E)$:

- **$V$ (Left Vertices):** The set of volunteers available for the event:
  $$V = \{v_1, v_2, \dots, v_n\}$$
  Each volunteer $v \in V$ is parameterized by:
  - $\text{skills}(v) \subseteq \Sigma$: the set of skill labels possessed by $v$.
  - $\text{avail}(v) \subseteq S$: the subset of slot IDs for which $v$ declared availability.
  - $\text{cap}(v) \in \mathbb{Z}_{\ge 0}$: the maximum number of shifts $v$ may be assigned.
  - $\text{pref}(v) \subseteq S$: the subset of slot IDs preferred by $v$.

- **$S$ (Right Vertices):** The set of shift slots to be staffed:
  $$S = \{s_1, s_2, \dots, s_m\}$$
  Each slot $s \in S$ is parameterized by:
  - $\text{role}(s)$: description of the role.
  - $[\text{start}(s), \text{end}(s))$: half-open time interval measured in integer minutes after midnight ($0 \le \text{start}(s) < \text{end}(s) \le 1440$).
  - $\text{req\_skill}(s) \in \Sigma \cup \{\text{null}\}$: mandatory skill required, or $\text{null}$ if open to all.

- **$E$ (Eligible Edges):** An edge exists between volunteer $v$ and slot $s$ if and only if volunteer $v$ satisfies both availability and skill prerequisites:
  $$E = \left\{ (v, s) \in V \times S \;\middle|\; s \in \text{avail}(v) \;\land\; (\text{req\_skill}(s) = \text{null} \;\lor\; \text{req\_skill}(s) \in \text{skills}(v)) \right\}$$

- **$P$ (Preferred Eligible Edges):**
  $$P = \left\{ (v, s) \in E \;\middle|\; s \in \text{pref}(v) \right\}$$

### A Priori Pruning Principle
Ineligible pairs $(v,s) \notin E$ are filtered out before variable instantiation. By instantiating decision variables **only** for eligible pairs $(v, s) \in E$, availability and skill constraints are enforced by construction, reducing the problem size and eliminating unneeded variables from the CP-SAT search space.

---

## 3. Decision Variables

For each eligible pair $(v, s) \in E$, define a binary decision variable:

$$x_{v,s} \in \{0, 1\} \quad \forall (v,s) \in E$$

$$\text{Interpretation: } x_{v,s} = \begin{cases} 
1 & \text{if volunteer } v \text{ is assigned to shift slot } s \\
0 & \text{otherwise}
\end{cases}$$

---

## 4. Objective Function: Coverage-First Priority

The global objective function maximizes a weighted sum of total filled slots and total satisfied preferences:

$$\max \quad Z = (|S| + 1) \sum_{(v,s) \in E} x_{v,s} + \sum_{(v,s) \in P} x_{v,s}$$

### Mathematical Proof of Coverage Dominance

**Theorem:** Under the objective function $Z$, any roster that covers $k + 1$ slots strictly outscores any roster that covers $k$ slots, regardless of the number of preference matches.

**Proof:**
1. Let $S_{\text{filled}} = \sum_{(v,s) \in E} x_{v,s}$ denote the number of filled slots in a candidate roster $R$.
2. Let $P_{\text{matched}} = \sum_{(v,s) \in P} x_{v,s}$ denote the number of satisfied preference edges in $R$.
3. By Constraint 1 (at most one volunteer per slot), each slot $s \in S$ can be assigned at most once. Therefore:
   $$0 \le P_{\text{matched}} \le S_{\text{filled}} \le |S|$$
4. Consider two valid candidate rosters, $R_A$ and $R_B$:
   - Roster $R_A$ fills $k + 1$ slots and satisfies $0$ preferences:
     $$Z(R_A) = (|S| + 1)(k + 1) + 0 = (|S| + 1)k + |S| + 1$$
   - Roster $R_B$ fills $k$ slots and satisfies the theoretical maximum possible preferences (all $k$ assignments are preferred, and $k \le |S|$):
     $$Z(R_B) = (|S| + 1)k + k \le (|S| + 1)k + |S|$$
5. Comparing the two objective values:
   $$Z(R_A) - Z(R_B) \ge \Big((|S| + 1)k + |S| + 1\Big) - \Big((|S| + 1)k + |S|\Big) = 1 > 0$$
6. Therefore, $Z(R_A) > Z(R_B)$ strictly holds. Gaining even a single additional filled slot yields an objective gain of $(|S| + 1)$, which strictly exceeds the maximum possible loss of $|S|$ preference points. Coverage always has absolute mathematical priority; preferences serve strictly as tie-breakers among rosters of equal maximum coverage. $\blacksquare$

### Equivalent Linear Form
In the OR-Tools CP-SAT implementation, the objective is represented as a single linear sum over all variables:

$$Z = \sum_{(v,s) \in E} w_{v,s} \cdot x_{v,s}$$

where the variable weight $w_{v,s}$ is:

$$w_{v,s} = \begin{cases}
|S| + 2 & \text{if } (v,s) \in P \quad (\text{preferred pair}) \\
|S| + 1 & \text{if } (v,s) \in E \setminus P \quad (\text{non-preferred pair})
\end{cases}$$

---

## 5. Constraints

### Constraint 1: Shift Exclusivity (At Most One Volunteer Per Slot)
Each shift slot requires at most one volunteer. Partial coverage is explicitly permitted to handle staff shortages:

$$\sum_{v : (v,s) \in E} x_{v,s} \le 1 \quad \forall s \in S$$

*(Note: Using $\le 1$ instead of $= 1$ ensures feasibility when staffing is limited, enabling the solver to return the best possible partial roster rather than reporting infeasibility).*

### Constraint 2: Volunteer Workload Capacity (Assignment Cap)
No volunteer may be assigned to more slots than their individually agreed maximum capacity:

$$\sum_{s : (v,s) \in E} x_{v,s} \le \text{cap}(v) \quad \forall v \in V$$

### Constraint 3: Shift Overlap Prevention (No Concurrent Shifts)
A volunteer cannot be physically present at two places simultaneously. Time intervals are treated as half-open $[start, end)$. Two slots $s_1$ and $s_2$ overlap if and only if:

$$\text{overlap}(s_1, s_2) \iff \text{start}(s_1) < \text{end}(s_2) \;\land\; \text{start}(s_2) < \text{end}(s_1)$$

For every volunteer $v \in V$ and for every pair of distinct slots $s_1, s_2 \in S$ ($s_1 \ne s_2$) such that $\text{overlap}(s_1, s_2)$ holds and $(v, s_1), (v, s_2) \in E$:

$$x_{v,s_1} + x_{v,s_2} \le 1$$

*Property:* Adjacent shifts (e.g., $s_1$ ending at 600 and $s_2$ starting at 600) satisfy $\text{start}(s_2) = \text{end}(s_1)$, so $\text{start}(s_2) < \text{end}(s_1)$ is false. Hence, back-to-back shifts do not conflict and can be served by the same volunteer.

---

## 6. CP-SAT Solver Implementation Architecture

The solver module is implemented in `shiftwise/solver_ortools.py` and adheres to the frozen interface:

```python
def solve(volunteers: Iterable[Any], slots: Iterable[Any]) -> SolverResult:
    ...
```

### Key Technical Implementation Details:
1. **Interface Flexibility:** Accepts `SimpleNamespace`, dataclasses, custom class instances, or dictionaries seamlessly via polymorphic attribute extraction (`_get_attr`).
2. **Deterministic Search:** CP-SAT solver parameters pin `random_seed = 42` to guarantee reproducible solution trajectories and deterministic tie-breaking across runs.
3. **Incumbent Extraction:** If search terminates with `FEASIBLE` (e.g., if a future runtime limit is imposed), the incumbent solution assignments and metrics are extracted and returned with `status = "feasible"`.
4. **Defensive Normalization:** When the solver finds no viable solution or is given empty inputs, the status is safely mapped to `"optimal"` (for empty inputs) or `"no_solution"`, and metrics are cleanly reported.
5. **Exact Timings:** Execution time is captured using `time.perf_counter()` to measure pure solver runtime in seconds with microsecond resolution.

---

## 7. Mathematical Tracing on Campus Tech Fest Scenarios

### Scenario A: Normal Staffing (`data/normal_staffing.json`)
- **Total slots:** $|S| = 10$
- **Coverage weight:** $|S| + 1 = 11$
- **Volunteer capacity:** 11 volunteers with varying availability and skills.
- **Optimal Roster Outcome:**
  - Status: `optimal`
  - Filled slots: $10 / 10$ (100.0% coverage)
  - Satisfied preferences: $4$
  - Total objective value: $11 \times 10 + 4 = 114$
- **Assignments:**
  - `av-setup` (540–660, req: AV) $\to$ **V10** (Jiya Kapoor, AV)
  - `av-demo` (660–720, req: AV) $\to$ **V02** (Bela Roy, AV)
  - `workshop-checkin` (660–720) $\to$ **V01** (Ari Sen)
  - `photo-booth` (600–720, req: Photo) $\to$ **V07** (Gautam Iyer, Photo) [Preferred]
  - `info-desk` (720–780) $\to$ **V09** (Ishaan Mehta) [Preferred]
  - `cleanup` (720–780) $\to$ **V06** (Farah Ali) [Preferred]
  - `registration-1` (540–600) $\to$ **V04** (Diya Rao)
  - `registration-2` (540–600) $\to$ **V03** (Chin Das) [Preferred]
  - `helpdesk-1` (600–660) $\to$ **V11** (Kabir Nair)
  - `helpdesk-2` (600–660) $\to$ **V08** (Hana Bose)

#### Highlight 1: Preference Sacrificed for Coverage
- **Conflict:** V01 prefers `av-demo` and is the **only** volunteer available for `workshop-checkin`. V02 is available for `av-demo` (and `av-setup`), but cannot cover `workshop-checkin`.
- `av-demo` and `workshop-checkin` both run 11:00–12:00 (minutes 660–720) and overlap.
- *Option 1 (Satisfy V01's preference):* Assign V01 $\to$ `av-demo`. Because `workshop-checkin` overlaps and no one else is available, `workshop-checkin` is uncovered.
  - Filled slots: 9. Preferences: $\le 5$. Objective $\le 11 \times 9 + 5 = 104$.
- *Option 2 (Prioritize Coverage):* Assign V02 $\to$ `av-demo` and V01 $\to$ `workshop-checkin`. Both positions are covered.
  - Filled slots: 10. Preferences: 4. Objective $= 11 \times 10 + 4 = 114$.
- **Solver Choice:** Option 2 ($114 > 104$). The model deliberately sacrifices V01's preference to maintain 100% coverage.

#### Highlight 2: Binding Assignment Cap
- V03 has `max_assignments = 1` and prefers both `registration-1` and `registration-2`.
- V03 cannot be assigned to both shifts due to the cap $\sum x_{\text{V03}, s} \le 1$.
- The solver assigns V03 to `registration-2` and V04 to `registration-1`, satisfying the cap constraint while maintaining full coverage.

---

### Scenario B: Limited Staffing (`data/limited_staffing.json`)
- **Total slots:** $|S| = 10$
- **Scarcity modification:** No AV-qualified volunteer is available for `av-setup` (V10's availability removed; V02 available only for `av-demo`; V01 available only for `av-demo` and `workshop-checkin`).
- **Optimal Roster Outcome:**
  - Status: `optimal`
  - Filled slots: $9 / 10$ (90.0% coverage)
  - Uncovered slot: `av-setup` (unavoidable vacancy)
  - Satisfied preferences: $4$
  - Total objective value: $11 \times 9 + 4 = 103$
- **Mathematical Explanation:**
  The eligibility set for `av-setup` is empty:
  $$\{v \in V \mid (v, \text{"av-setup"}) \in E\} = \emptyset$$
  Because $\sum_{v} x_{v, \text{"av-setup"}} = 0$, `av-setup` cannot be filled. The solver fills all remaining 9 slots and reports `av-setup` as explicitly uncovered.

---

## 8. Viva Voce Quick-Reference Guide

| Question | Core Mathematical Answer |
|---|---|
| **Why CP-SAT over ILP/MIP?** | CP-SAT combines SAT conflict-driven clause learning with integer programming cuts and domain propagation. For finite discrete assignment problems with discrete logic constraints (exclusivity, overlap), CP-SAT solves instantaneously with zero numerical drift. |
| **Why not standard Maximum Bipartite Matching (Hopcroft-Karp)?** | Standard matching assumes a 1-to-1 unweighted relationship. Our problem incorporates multi-capacity vertices ($\text{cap}(v) > 1$), non-adjacent edge conflict exclusions (interval overlaps), and a hierarchical multi-tier objective. |
| **How are overlaps modeled efficiently?** | Using interval half-open logic $[start, end)$. Mutual exclusion is enforced pairwise across all overlapping pairs for each volunteer: $x_{v,s_1} + x_{v,s_2} \le 1$. |
| **Why does the solver not crash when a slot cannot be covered?** | The slot constraint uses $\le 1$ instead of $= 1$. Partial coverage is mathematically feasible, so the solver maximizes coverage without constraint violation. |
| **Can OR-Tools and PuLP produce different rosters?** | Yes. When multiple rosters achieve the exact same maximum objective value, different search heuristics or variable visit orderings can find different optimal rosters. Both solutions are mathematically optimal. |
