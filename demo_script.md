# ShiftWise mini-project demo script

This walkthrough uses Darshan-authored scenarios in `data/`. On the verified Windows/Python 3.14.4 environment, both solvers returned 10/10 filled with 3 preference matches for normal staffing and 9/10 with 3 preference matches for limited staffing; `av-setup` was the vacancy. Assignment identities can vary, so point to the roster currently shown by the app.

## 1. Introduce the problem

“ShiftWise helps a campus event coordinator assign volunteers to individual role slots. Each volunteer has skills, availability, a maximum assignment count, and preferred slots. Our goal is to fill as many positions as possible while obeying hard constraints.”

## 2. Run normal staffing

Select **Normal staffing**, choose **OR-Tools** or **PuLP**, and click **Run optimization**. State the verified score: **10 of 10 slots filled, with 3 preference matches**. Show the roster, coverage percentage, preferences, and per-volunteer counts.

## 3. Explain eligibility, a skill exclusion, and the objective

Point out that V05 lists the photo-booth slot as available but does not have the required Photo skill; that pair is not eligible. Explain that V01 prefers AV demo support but is the only candidate for workshop check-in. The two slots overlap, so keeping full coverage requires V01 at check-in and another qualified volunteer at demo. This is an example of coverage taking priority over a preference.

V03's assignment cap is demonstrated by two eligible non-overlapping positions, registration-1 and info-desk. V03 can cover at most one because its cap is one; the overlap between the two registration positions is a separate constraint.

## 4. Run limited staffing

Select **Limited staffing** and run a solver. State the verified score: **9 of 10 slots filled, with 3 preference matches**. Point to `av-setup` as uncovered: it requires AV and no AV-qualified volunteer is available for it.

## 5. Compare both solvers

Choose **Compare both** and run optimization. Compare status, filled/total count, preferences, and elapsed time. Both solvers have the same verified coverage and preference scores on these scenarios. Their volunteer assignments may differ while remaining equally optimal.

## 6. Explain the discrete mathematics

“Volunteers form one side of a bipartite graph and individual role slots form the other. An edge exists only when a volunteer is available and has any required skill. A binary decision variable says whether an eligible edge is selected. Constraints enforce at most one volunteer per slot, assignment caps, and no overlapping assignments for the same volunteer.”

“The objective maximizes `(number of slots + 1) × filled slots + preference matches`. Since preferences can add at most one point per filled slot, gaining one filled slot always outweighs any possible preference loss.”

## 7. Finish with CSV export

Download the displayed roster as CSV. In compare mode, the CSV includes both solver rosters. Close by noting that the application runs locally and uses deterministic optimization without a generative AI service.
