# ReliefOpt Vadodara flood scenarios

These two small, fictional scenarios model resource allocation during a Vadodara flood response. They are designed for a deterministic PDL demonstration of combinatorics, bipartite matching, eligibility, constraints, and partial coverage. They are not live incident data or operational dispatch instructions.

## Scenario records

Each scenario has **11 response resources** and **10 incidents**. Resource records use the shared `Volunteer` fields (`id`, `name`, `skills`, `available_slot_ids`, `max_assignments`, `preferred_slot_ids`); incident records use the shared `ShiftSlot` fields (`id`, `role`, `start_time`, `end_time`, `required_skill`). The JSON top-level `incident_triage` map contains UI-only RED/YELLOW/GREEN display labels keyed by incident ID. It is separate from solver records and is not an optimization weight.

The units include two NDRF boats, two ALS ambulances, a Fire Brigade heavy rescue team, a mobile medical van, a supply drone, a Fire Brigade rescue unit, an NDRF flood response team, a Civil Defence evacuation unit, and a relief supply truck. Skills include `Boat`, `Water_Rescue`, `ALS`, `Medical`, `Heavy_Rescue`, `Supply`, `Drone`, `Evacuation`, and `Logistics`.

The ten incidents are `rooftop-flood-rescue`, `trauma-evacuation`, `oldage-home-flood`, `icu-transfer`, `clean-water-delivery`, `structural-collapse-rescue`, `medicine-delivery`, `food-relief-convoy`, `debris-clearance`, and `shelter-evacuation`. Times are integer minutes after midnight on a single fictional response day. Intervals use the shared half-open rule `[start_time, end_time)`.

## Deliberate demonstrations

- **Skill exclusion:** `NDRF-TEAM-01` lists `rooftop-flood-rescue` in its availability but lacks the required `Boat` skill, so it is not eligible. `NDRF-BOAT-01` and `NDRF-BOAT-02` have the required capability when available.
- **Availability exclusion:** In normal staffing, both NDRF boats are listed for `rooftop-flood-rescue`. In limited staffing, neither boat is available for that incident window. Other units either lack `Boat` or are not available for it.
- **Overlap conflict:** `rooftop-flood-rescue` and `oldage-home-flood` run from 09:00 to 11:00. One boat cannot cover both at once; two boats can cover them separately in normal staffing. The ALS incidents also overlap, so the two ALS ambulances must be allocated across them without double-booking either unit.
- **Binding capacity cap:** `DRONE-SUPPLY-01` is eligible for and prefers the non-overlapping `clean-water-delivery` and `food-relief-convoy` incidents, but its cap is one. It can take at most one; `SUPPLY-TRUCK-01` and `CIVIL-DEFENSE-01` provide alternatives. `FIRE-HEAVY-01` has a cap of one while eligible for the non-overlapping structural rescue and debris clearance incidents; `FIRE-RESCUE-01` is another Heavy_Rescue-capable option.
- **Preferences:** Several units prefer incidents for which they have matching availability and skills. The solvers use eligible preferred assignments as secondary objective points after coverage. Different tied assignments are allowed.
- **Unavoidable shortage:** Limited staffing removes rooftop availability from both Boat units. No other unit has the `Boat` skill, so `rooftop-flood-rescue` has no eligible edge and cannot be covered. The mathematical model may still cover the other nine incidents and return a valid partial allocation.

## Triage display and optimization scope

The UI shows RED (critical), YELLOW (urgent), and GREEN (routine) labels from `incident_triage` to give the dispatcher and teacher context. The map is display metadata only. The current shared solver interface contains skills, availability, caps, preferences, and incident time windows, but no severity field. Both current solver modules maximize total coverage first and preference matches second; they do **not** optimize a severity-weighted triage score. The UI therefore labels the score as preference matches and does not claim that RED incidents mathematically outrank other incidents. Adding severity to the optimization would require a coordinated shared model and solver change outside these dataset/app files.

## Expected scenario outcomes

Normal staffing is constructed so all ten incidents have a feasible allocation. Limited staffing is constructed so rooftop rescue has no eligible resource; its expected maximum coverage is nine of ten. Run both configured solvers to verify actual status, coverage, preference score, and assignments. Assignment identities and elapsed times can vary by solver/backend while satisfying the same model.

These are deterministic teaching fixtures. They do not model routing, travel time, resource geography, changing flood conditions, multiple required units per incident, or real-time reassignment.
