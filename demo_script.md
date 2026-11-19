# ShiftWise mini-project demo script

This is a repeatable walkthrough using Darshan's existing normal- and limited-staffing scenarios (11 volunteers and 10 individual slots, as documented in `data/README.md`). It does not prescribe, create, or revise any volunteer or slot records. Use the records currently present in `data/` and describe only outcomes observed when the app is run.

## 1. Introduce the problem

“ShiftWise helps a campus event coordinator assign volunteers to individual role slots. Each volunteer has skills, availability, a maximum assignment count, and preferred slots. The goal is to cover as many positions as possible without violating hard constraints.”

## 2. Run normal staffing

Select **Normal staffing**, choose one solver, and run optimization. Darshan's data notes describe this scenario as having a feasible full-coverage roster; confirm the live result before stating the exact score. Point to the roster and explain the displayed filled/total slots, coverage percentage, preference matches, solver status, and assignment counts per volunteer. Do not claim a particular volunteer-to-slot assignment unless it appears in the live result.

## 3. Explain eligibility and one exclusion

Choose one assignment visible in the roster. Check the corresponding volunteer's availability and skills against the slot. Then identify one ineligible pair from the actual dataset—for example, an unavailable volunteer or a volunteer lacking the slot's required skill. Explain that only eligible volunteer-slot pairs are candidates for assignment.

## 4. Run limited staffing

Select **Limited staffing** and run the same solver. Darshan's dataset notes identify `av-setup` as the deliberate shortage: no AV-skilled volunteer is available for that slot. Confirm that the live result leaves it uncovered, then explain that the solver returns a useful partial roster rather than requiring every slot to be filled.

## 5. Compare both solvers

Choose **Compare both** and run optimization. Compare normalized status, filled slots, preference matches, and elapsed time. The two rosters do not need identical volunteer identities: if multiple assignments have the same optimal coverage and preference score, either roster can be valid.

## 6. Explain the discrete mathematics

“Volunteers form one side of a bipartite graph and role slots form the other. An edge connects a volunteer to a slot only when availability and skill requirements are satisfied. A binary decision variable indicates whether an eligible edge is selected. Additional constraints enforce one volunteer per slot, each volunteer's assignment cap, and no overlapping shifts for the same volunteer.”

“The objective gives each filled slot a weight of `number_of_slots + 1`, then adds preference points. Since preference points can never exceed the number of slots, coverage always has priority.”

## 7. Finish with CSV export

Download the displayed roster as CSV and briefly show the exported columns. Close by noting that the prototype runs locally and uses deterministic optimization; it does not call a generative AI service.

## Presenter checklist

- [ ] Confirm the current normal scenario and its actual observed coverage.
- [ ] Confirm the current limited scenario and identify its actual uncovered slot.
- [ ] Be ready to explain one eligible pair and one ineligible pair from the current records.
- [ ] Run each solver and compare scores, not exact assignment identities.
- [ ] Try the CSV download before presenting.
- [ ] Do not state unverified outcomes or invent sample records during the walkthrough.
