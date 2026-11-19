# ReliefOpt: Disaster Relief Resource Allocation
## Discrete Mathematics Study & Viva Preparation Guide

**Course:** Program Development Laboratory (PDL) / Discrete Mathematics  
**Topic:** Dynamic Disaster Resource & Task Allocation using Combinatorics, Bipartite Graph Matching, and Deterministic Constraint Optimization (OR-Tools CP-SAT & PuLP)

---

## 1. Project Overview & Mathematical Foundation

### The Core Problem
In sudden-onset disasters (e.g., urban flooding like the Vadodara 2024 floods), emergency coordinators face extreme scarcity. Multiple emergency distress calls arrive simultaneously across different geographical sectors, while rescue resources (NDRF boats, ALS ambulances, medical teams, drone delivery units) have limited availability, specialized capabilities, time-window conflicts, and operational shift capacities.

Standard naive dispatching (**"first-come, first-served"** or **"greedy nearest-first"**) fails catastrophically:
* Advanced Life Support (ALS) ambulances get dispatched to minor sprains, leaving cardiac or polytrauma victims without care.
* Teams get double-booked across overlapping time windows in distant sectors.
* Units exceed human fatigue limits.

### Mathematical Framework
ReliefOpt models the entire city's response as a **Constrained Maximum-Weight Bipartite Assignment Problem**:
1. **Bipartite Graph $G = (R \cup I, E)$**:
   - Partition $R$: Emergency Response Units (Left Vertices).
   - Partition $I$: Disaster Distress Incidents / Tasks (Right Vertices).
   - Edge Set $E \subseteq R \times I$: Valid assignment possibilities connecting unit $r$ to incident $i$.
2. **Pruned Eligibility by Construction**:
   An edge $(r, i) \in E$ exists if and only if:
   - Resource $r$ has the required capability/equipment (e.g., `Boat` for flooded sectors, `ALS_Medical` for severe trauma, `Heavy_Rescue` for collapsed structures).
   - Incident time interval falls within unit $r$'s operational shift window.
   - Any pair failing these conditions is eliminated *a priori*, reducing the combinatorial search space.
3. **Hard Constraints**:
   - **Exclusivity**: Each incident assigned to at most 1 primary response unit ($\sum_{r} x_{r,i} \le 1$).
   - **Workload Capacity**: Each unit handles at most $\text{cap}(r)$ tasks ($\sum_{i} x_{r,i} \le \text{cap}(r)$).
   - **Interval Conflict / Overlap Exclusion**: No unit can be in two overlapping incidents simultaneously ($x_{r,i_1} + x_{r,i_2} \le 1$ for all overlapping half-open intervals $[start, end)$).
4. **Hierarchical Triage Objective (Coverage + Severity Prioritization)**:
   - Critical incidents (**RED / Life-Threatening**) must strictly dominate routine tasks.
   - The objective scales triage points such that saving one higher-severity victim strictly outweighs any combination of lower-severity choices.

---

## 2. 4-Person Role Distribution & Viva Voce Guide

---

### Member 1: Darshan — Dataset Modeling & Operations UI

#### What Darshan Studied:
1. **Discrete Scenario Modeling & Graph Generation**:
   - How to construct synthetic bipartite graph instances that represent realistic operational stress without requiring a live external database.
   - Designing the "Vadodara Flood Scenario" to demonstrate edge pruning: inaccessible flooded roads requiring amphibious/boat capabilities, severe trauma triage, and multi-incident capacity caps.
2. **Shortage & Degraded State Demonstration**:
   - Creating a "Normal Staffing" scenario (full coverage feasible) vs. a "Catastrophic Shortage" scenario where $|I| > \sum \text{cap}(r)$, mathematically forcing the solver into partial matching and highlighting unserved distress calls.
3. **Deterministic UI Design**:
   - Presenting combinatorial matchings as an emergency dispatch manifest with triage color codes (🔴 Red = Critical, 🟠 Yellow = Urgent, 🟡 Green = Stable).
   - Visualizing unit utilization meters and CSV export for field operations.

#### Viva Questions & Model Answers for Darshan:
* **Q1: Why did you build two separate scenarios (Normal vs. Overwhelmed)?**  
  *Answer:* To prove that our optimization model is robust. In normal conditions, it achieves 100% coverage. In catastrophic conditions (overwhelmed resources), the model does not fail or crash with an infeasibility exception; instead, because we formulated the slot constraint as an inequality ($\sum x \le 1$), it finds the maximal feasible partial matching and explicitly flags unserved victims for emergency escalation.
* **Q2: Why not just use real-time GPS and a live database like MongoDB or Firebase?**  
  *Answer:* Our goal was mathematical determinism and explainability for discrete optimization. Live external APIs introduce non-deterministic network latency, auth keys, and external points of failure. By bundling verified, reproducible scenario records, every student, evaluator, and researcher can benchmark both solvers on identical graph topologies.
* **Q3: How are overlapping times represented in your dataset?**  
  *Answer:* Times are integer minutes after midnight (e.g., 540 = 09:00 AM) using half-open intervals $[start, end)$. If Task A ends at 600 (10:00 AM) and Task B starts at 600 (10:00 AM), they do not overlap ($start_B < end_A$ is false), allowing immediate back-to-back dispatch.

---

### Member 2: Shriyans — Google OR-Tools CP-SAT Solver & Mathematical Formulation

#### What Shriyans Studied:
1. **Constraint Satisfaction Problems (CSP) & SAT Solvers**:
   - The CP-SAT engine: combining Constraint Programming (domain reduction, constraint propagation) with Boolean Satisfiability (CDCL — Conflict-Driven Clause Learning) and Integer Programming cutting planes.
2. **Binary Decision Variable Formulation**:
   - Formulating $x_{r,i} \in \{0, 1\}$ strictly for eligible edges $(r,i) \in E$.
   - Why creating variables only for eligible pairs is mathematically superior to adding $x_{r,i} = 0$ penalty constraints (it prunes the branch-and-bound search tree exponentially).
3. **Hierarchical Triage Objective Proof**:
   - Formulating the mathematical weighting function that guarantees triage dominance:
     $$\max \quad \sum_{(r,i) \in E} W(i) \cdot x_{r,i}$$
     where $W(i) = (\text{Triage Weight}) \times (|I| + 1) + \text{Preference/Proximity}$.
   - Proving that no combination of minor GREEN calls can ever displace a single critical RED life-or-death rescue.

#### Viva Questions & Model Answers for Shriyans:
* **Q1: Why did you choose OR-Tools CP-SAT instead of a simple greedy algorithm?**  
  *Answer:* A greedy algorithm assigns the closest available unit to the first caller. In disasters, this leads to suboptimal resource exhaustion: e.g., an ALS boat gets assigned to a minor supply run at 09:05 AM, leaving a family trapped in rising waters at 09:10 AM with no available boat. CP-SAT considers the global bipartite graph simultaneously, finding the global Pareto-optimal matching across all constraints.
* **Q2: How do you enforce the non-overlapping shift constraint mathematically?**  
  *Answer:* For each resource unit $r$, and for every pair of incidents $i_1, i_2$ where unit $r$ is eligible for both and their time intervals overlap ($\text{start}_1 < \text{end}_2 \land \text{start}_2 < \text{end}_1$), we generate the mutual exclusion constraint:
  $$x_{r, i_1} + x_{r, i_2} \le 1$$
  CP-SAT converts these into Boolean conflict clauses, preventing double-booking by construction.
* **Q3: How do you mathematically guarantee that Critical (RED) incidents are prioritized over routine ones?**  
  *Answer:* We assign base weights according to triage severity: Critical (RED) = 100, Urgent (YELLOW) = 40, Routine (GREEN) = 10. We multiply each severity tier by a scale factor strictly greater than the maximum possible sum of lower-tier rewards. Thus, mathematically:
  $$W_{\text{RED}} > \sum_{i \in I_{\text{GREEN}}} W(i)$$
  The solver can never gain higher objective points by sacrificing a RED patient to serve multiple GREEN ones.

---

### Member 3: Atharva — PuLP Solver & Integer Linear Programming (ILP)

#### What Atharva Studied:
1. **Integer Linear Programming (ILP) vs. Constraint Programming (CP)**:
   - Formulating the identical disaster allocation model in PuLP as a pure 0-1 Binary Integer Linear Program:
     $$\max \mathbf{c}^T \mathbf{x} \quad \text{s.t.} \quad A\mathbf{x} \le \mathbf{b}, \quad \mathbf{x} \in \{0, 1\}^{|E|}$$
2. **Underlying Optimization Engines (CBC / HiGHS)**:
   - How PuLP interfaces with linear programming backends (COIN-OR CBC and HiGHS).
   - The Branch-and-Cut algorithm: solving continuous LP relaxations using Simplex, generating cutting planes (Gomory cuts), and branching on fractional variables until all $x_{r,i} \in \{0, 1\}$.
3. **Solver Performance Comparison & Equivalence**:
   - Benchmarking OR-Tools CP-SAT against PuLP on the same bipartite instances.
   - Demonstrating that while both solvers arrive at identical optimal objective values (triage points and covered incidents), their search paths and execution times differ.

#### Viva Questions & Model Answers for Atharva:
* **Q1: What is the fundamental difference between how PuLP and OR-Tools CP-SAT solve this model?**  
  *Answer:* PuLP formulates the problem as an Integer Linear Program (ILP). It starts by relaxing the binary constraint $x \in \{0, 1\}$ to continuous $0 \le x \le 1$ and solves it via the Simplex algorithm, then applies Branch-and-Bound and cutting planes. OR-Tools CP-SAT is a Constraint Programming solver based on SAT (Boolean Satisfiability) technology. It uses Conflict-Driven Clause Learning (CDCL) and domain filtering to prune invalid assignments before applying integer bounds.
* **Q2: Why do OR-Tools and PuLP sometimes return different volunteer/team assignments for the same scenario?**  
  *Answer:* Both solvers maximize the exact same objective function. However, when multiple distinct rosters achieve the exact same maximum objective score (alternate optima), OR-Tools and PuLP may break ties differently due to their different internal variable ordering and search heuristics. Both solutions are mathematically 100% optimal.
* **Q3: What happens during LP relaxation if integrality is ignored?**  
  *Answer:* In pure bipartite matching with standard degree constraints, the constraint matrix is Totally Unimodular (TUM), meaning the LP relaxation naturally yields integer solutions. However, because our model introduces interval overlap clique constraints ($x_{r, i_1} + x_{r, i_2} \le 1$), the matrix loses total unimodularity, requiring true integer branch-and-bound to prevent fractional allocations (like assigning 0.5 of an ambulance).

---

### Member 4: Manas — Shared Data Contracts, Invariants & Graph Validation

#### What Manas Studied:
1. **Graph Invariants & Well-Formedness Checks**:
   - Designing the formal validation layer that runs *before* any solver is invoked.
   - Verifying graph invariants: graph bipartition, node uniqueness, valid interval boundaries ($end > start$), non-negative capacities ($\text{cap}(r) \ge 0$), and valid capability references.
2. **Hall's Marriage Theorem & Matchability Conditions**:
   - Understanding Hall's Condition for bipartite matching: a complete matching from $I$ to $R$ exists if and only if for every subset $S \subseteq I$, the neighborhood $|N(S)| \ge |S|$.
   - When Hall's condition is violated (e.g. 5 flooded rescue requests, but only 2 boat units in $N(S)$), shortage is inevitable. The validation and metrics layer detects and quantifies this deficiency.
3. **Computational Complexity ($P$ vs. $NP$)**:
   - Unconstrained bipartite matching is solvable in polynomial time $O(V \cdot E)$ using the Hopcroft-Karp algorithm.
   - However, adding interval conflict exclusions turns the problem into a variant of the **Maximum Weight Independent Set on an Interval Conflict Graph**, which is $NP$-hard in the general case, mathematically justifying the use of CP-SAT and ILP solvers.

#### Viva Questions & Model Answers for Manas:
* **Q1: Why is an explicit validation layer necessary if the solvers already enforce constraints?**  
  *Answer:* Solvers are mathematical engines; if fed corrupted data (e.g., negative caps, non-existent incident IDs, or inverted times where $end \le start$), they can return misleading results, loop indefinitely, or throw cryptic low-level C++ exceptions. The validation layer acts as a semantic firewall, guaranteeing that every input satisfies graph invariants with actionable error messages before optimization begins.
* **Q2: Why can't we just use the Hopcroft-Karp maximum bipartite matching algorithm?**  
  *Answer:* Hopcroft-Karp only solves unweighted, 1-to-1 bipartite matching with no conflicting side-constraints. Our problem has multi-capacity units ($\text{cap}(r) > 1$), non-overlapping temporal constraints (two incident intervals cannot overlap for the same unit), and multi-tier triage weights (RED > YELLOW > GREEN). These side-constraints make the problem $NP$-hard, requiring general constraint solvers like CP-SAT and PuLP.
* **Q3: How are metrics calculated independently of the solver output?**  
  *Answer:* Our `calculate_metrics` function takes the returned assignment pairs and audits them against the raw scenario records. It recalculates total covered incidents, verifies that no unit exceeded its cap, confirms that no overlapping shifts were assigned, and computes total triage points. This ensures that the UI does not blindly trust solver output without independent verification.

---

## 3. Summary Cheat-Sheet for the Entire Team

| Concept | Definition in ReliefOpt |
|---|---|
| **Bipartite Graph** | $G = (R \cup I, E)$ dividing nodes into Response Resources $R$ and Disaster Incidents $I$. |
| **Decision Variable** | Binary $x_{r,i} \in \{0, 1\}$, instantiated strictly for eligible pairs. |
| **Shift Exclusivity** | $\sum_{r} x_{r,i} \le 1$: at most 1 team per incident (allows partial matching during shortages). |
| **Unit Workload Cap** | $\sum_{i} x_{r,i} \le \text{cap}(r)$: protects rescue teams from fatigue. |
| **Interval Conflict** | $x_{r, i_1} + x_{r, i_2} \le 1$: prevents scheduling a unit to two overlapping tasks. |
| **Coverage Dominance** | Scaling triage weights so saving 1 Critical life strictly outranks any set of minor tasks. |
| **CP-SAT vs PuLP** | CP-SAT uses SAT-based clause learning; PuLP uses LP relaxation and Branch-and-Cut Simplex. |
