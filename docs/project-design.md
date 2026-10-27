Read AGENTS.md and docs/project-design.md. This is a feasibility check only. Use plan mode: do not write cleaning or extraction code, and do not modify data/raw/.

## Project
I'm replicating Deneault (2023, AEJ: Policy), a dosage DiD of Louisiana's FAFSA graduation mandate, in all 15 states with a FAFSA mandate or related policy: Louisiana, Illinois, Alabama, Texas, Colorado, Maryland, California, Indiana, New Hampshire, Nebraska, Oklahoma, New York, New Jersey, Connecticut, and Pennsylvania. In each state I estimate her specification (school FE, class FE, D_s × Post, controls, school-size weights, school-clustered SEs) for FAFSA completion (first stage) and college enrollment (reduced form), with her controls plus free/reduced-price lunch, income and additional NCES variables. I then pool the state estimates with a Bayesian hierarchical model (Meager 2019, AEJ: Applied), and study heterogeneity by school traits, likely undocumented-student share, and how each state enforces its mandate. Unit: school × graduating class. Dose D_s = 1 − school's average FAFSA completion rate (FCR) over the two classes just before the last pre-mandate class (e = −3 and −2), excluding partial-rollout years, as in Deneault (Louisiana: dose 2015–16, reference 2017). The last pre-mandate class (e = −1) is the reference period. Earlier classes in any source are pre-trend checks. docs/project-design.md section 2 lists the dose, reference and post years for every state. FCR = completed FAFSAs through June ÷ high school graduates (Deneault's definition); grade-12 enrollment is the fallback.

The states differ in policy type (graduation requirement; offer/confirm or tracking only; Colorado's grant-school-only requirement; Maryland's support duty), and some are too recent for enrollment data (New Jersey: class of 2025) or for any post-mandate data (Connecticut, Pennsylvania: class of 2027). docs/project-design.md section 0.2 has my current understanding of each state's policy; treat it as a starting point to verify, not as fact.

I will be getting data for all 15 states. Sources are in docs/source-notes.md. FSA FAFSA completion files, EDFacts graduation rates, and the NCES Common Core of Data are in data/raw/US/.

## For each state, check and report

A. Policy: the policy type (graduation requirement vs. offer/confirm vs. other), the first covered class, any partial-rollout year, repeal dates, opt-out rules (and opt-out counts if published), and concurrent policies (e.g., free-college or aid programs). Also record who the mandate binds (students vs. districts vs. specific schools), who can grant a waiver (parent/adult student only, or counselor/principal/superintendent too), whether the diploma is withheld, what the state agency does (forms, reporting, monitoring) vs. what is left to districts, accompanying supports (outreach, counseling, completion events), and whether the state has its own alternative aid application for undocumented students. These are candidate predictors in the pooling model. Cite a statute or state agency source for each fact.

B. Outcome: college enrollment by high school and graduating class.
- Count vs. rate
- Data source (Clearinghouse vs. state records)
- Timing window (fall-only vs. 12/16-month)
- In-state only or all institutions
- In-state vs. out-of-state split
- 2-year/4-year split
- Years covered, and the expected release date of the next class
- Suppression rules

C. Denominators: graduate counts, ACGR, and adjusted 9th-grade cohort. Include the years covered, and whether cohort counts exist 3 years before the earliest class.

D. Controls:
- Deneault's: school-average ACT/SAT and the years of universal school-day testing; race shares and total enrollment (state files or NCES CCD).
- Added: free/reduced-price lunch, direct certification and Community Eligibility Provision status (note years where FRL breaks); income (NCES EDGE School Neighborhood Poverty Estimates; ACS-ED district profiles); counselors per student and English learner share (Civil Rights Data Collection, which years); Title I, locale, charter, magnet (CCD); distance to the nearest 2-year and 4-year college (EDGE geocodes + IPEDS). Most of these are federal; report state-by-state gaps and years covered.

E. Identifiers: NCES school ID, a state ID that maps to NCES, or name only.

F. Sample-restriction fields: school type (special ed, virtual, alternative) and inputs for the student/teacher ratio.

G. Format: Excel or PDF or Tableau that can be downloaded as Excel, whether PDFs have a text layer, and changes in columns or definitions across years.

H. Enforcement and compliance data: published waiver/opt-out counts by district or school, state compliance reports, and anything showing how districts implement the mandate.

I. Alternative aid applications: whether counts of the state's alternative application (e.g., CADAA, TASFA, Illinois Alternative Application, CASFA, MSFAA, NJAFAA, NYS DREAM Act application) exist by high school, and for which years.

## Timing feasibility (per state)
- With FSA data starting at the class of 2015: confirm the dose classes (e = −3, −2) and reference class (e = −1) in docs/project-design.md section 2 are available and clean (no partial-rollout year) in each state. Flag states whose dose or reference includes the COVID classes (2020–21) or the class of 2024 (FAFSA rollout delay). How many pre-years for the event study, and how many post-years for the first stage and for enrollment?
- Where do the classes of 2020–21 (COVID), the class of 2024 (FAFSA rollout problems), and the October 2016 FAFSA launch / prior-prior year change (first affecting the class of 2017 and also then the class of 2018) fall relative to the dose window, the reference class, and the mandate?
- For Connecticut and Pennsylvania: confirm that no post-mandate data exist yet, and check the class of 2026 for anticipation.

## Design feasibility (flag issues; don't decide)
1. Dose variation. If FSA files are present, compute the pre-period FCR distribution by state (dose window only) and report the share of schools at low dose (pre-FCR near 1) and at high dose. There are no untreated schools within a state, so the within-state comparison is high vs. low dose.
2. Common post-window and estimation window. Confirm that e = 0 (the first covered class) exists for both outcomes in every state used for pooling, list which states also have e = 1, and report how many schools stay in a balanced panel over Deneault's window (e = −4 to +1, or to e = 0 where only one post class exists) in each state.
3. Pooling comparability. For Meager-style pooling, list every way the outcome or FCR differs across states (policy type, enrollment definition, window, denominator, suppression), and whether each can be harmonized. Note whether school-level data, not just state summaries, is available.
4. Heterogeneity. For each proposed dimension (counselor ratio, neighborhood poverty, rural locale, charter, English learner share, distance to college, alternative-application state, enforcement type), report whether the data exist for all states and years and whether there is enough variation within each state.
5. Louisiana validation. Confirm I have what's needed to reproduce Deneault Table 2: 259 schools, classes of 2014–2019, mandate effective for the class of 2018.

## Design
- Unit: school s × graduating class t. Within each state, all schools are treated at the same time (no untreated schools, no staggering within state).
- Dose (Deneault's window): pre-period FCR averaged over e = −3 and −2 (excluding partial-rollout years); D_s = 1 − pre-FCR, on the same 0–1 scale in every state. The last pre-mandate class (e = −1) is the reference period. Sensitivity: a pre-COVID dose (2018–19) for states whose dose includes 2020–21.
- Headline per state (Deneault's specification): Y_st = α_s + λ_t + β·(D_s × Post_t) + X_st′γ + ε_st for Y = FCR and Y = enrollment, with Deneault's weights (average pre-period total students ÷ grades taught), sample restrictions, and school-clustered SEs. IV = reduced form ÷ first stage, reported as secondary.
- Event study: D_s × class dummies, omitting the reference class, as the parallel-trends diagnostic in every state.
- Controls: Deneault's (race shares, ACT/SAT, enrollment and its square) plus the additions in D. Time-invariant traits are absorbed by school FE, so they enter as time-varying values, pre-period values × class FE, or pre-period values × D_s × Post for heterogeneity. Never control for ACGR or enrollment.
- Common post-window for pooling: e = 0. Estimation window for the headline regression: Deneault's e = −4 through e = +1 (Louisiana 2014–2019), or through e = 0 where only one post class exists, balanced panel of schools; sensitivity e = −4 to 0 in every state. The event study uses all available years. Louisiana ends at 2024 (repeal); New Hampshire's only post class is 2024. Flag, don't drop, COVID classes and the class of 2024.
- 2025 adopters (Nebraska, Oklahoma, New Jersey, New York): their reference class is the class of 2024, so also run a triple difference against never-adopting states (D_s × Post × Adopt) for the first stage.
- Replication check: reproduce Louisiana Table 2 (first stage 0.421, RF 0.133, IV 0.334; 259 schools; classes 2014–2019; mandate class of 2018) before running other states.
- Pooling: Meager hierarchical model on one β and SE per state and outcome, with policy type as a state-level covariate (at most 1–2 state-level covariates). Connecticut and Pennsylvania serve as an out-of-sample test: predict their effects from the posterior predictive now, and check later. Prior-sensitivity and leave-one-state-out checks.
- Heterogeneity: interactions of D_s × Post with pre-period school traits; enforcement design across states; schools with high vs. low likely-undocumented share, in states with vs. without an alternative application; outcomes such as completions ÷ submissions, filing timing, 2-year vs. 4-year enrollment, and graduation (ACGR).
- Robustness: Deneault's checks (pre-period ACT and race × class FE, group-specific trends, alternative intensity measures, reshuffled D_s placebo with 1,000 draws), placebo runs on never-adopting states, Rambachan & Roth bounds, Khan (2026)-style cross-state comparison.

## Deliverables
1. docs/state-metadata.md: one row per state with policy fields (A), outcome-definition fields (B), and enforcement and alternative-application fields (H, I), each with a source link.
2. A coverage table in docs/progress.md. Rows are A–I plus the timing items; columns are the 15 states; cells say present / partial / missing, with column names and years.
3. A ranked list of risks and open questions, starting with anything that would rule a state out of the first-stage or reduced-form pool.
4. A list of candidate never-adopting comparison states, with any exclusion reason (law passed, repealed, pending) and FSA coverage, with sources, marked (this is not a high priority, ignore for now).
5. A list of data requests to make (agency, contact, what to ask for), e.g., Maryland MLDS Center, NYSED, Nebraska CCPE/NDE.

## Rules
- Cite a source for every policy fact.
- Mark anything uncertain rather than guessing.
- Save any exploratory code in code/explore/ and run it with `uv run --locked`.
