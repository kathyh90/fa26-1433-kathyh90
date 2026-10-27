# State data requirements

Applies to all 15 states (LA, IL, AL, TX, CO, MD, CA, IN, NH, NE, OK, NY, NJ, CT, PA). A state can enter the first-stage pool (FAFSA completion) without entering the reduced-form pool (college enrollment), so the must-haves are split by outcome.

## Must-have for the first stage (FAFSA completion)
- ≥3 clean pre-mandate classes from class of 2015 onward in FSA data, excluding any partial-rollout year: the pre-mandate class one year before the mandate year is the reference period, kept out of the dose window; the two years before the reference period set the dose (pre-period FCR)
- ≥1 post-mandate class in FSA data (the first covered class, e = 0, is the common post-window for pooling)
- Graduate counts per school per class (FCR denominator, as in Deneault); grade-12 enrollment from CCD as fallback, flagged
- School identifier linkable to NCES and FSA (NCES ID, state ID with crosswalk, or name+city for fuzzy matching; log every match)
- Documented policy dates: first covered class, partial-rollout year, repeal date, opt-out rules

## Must-have for the reduced form (college enrollment)
- Everything above, plus:
- College enrollment by individual high school × graduating class (not state or district totals)
- ≥2–3 pre-mandate classes of the enrollment outcome (event study / pre-trends)
- ≥1 post-mandate class (e = 0); note when the next class is expected to be released
- Enrollment definition held fixed over time within the state

## Needed for full Deneault replication
- ACGR and adjusted 9th-grade cohort (incl. cohort counts 3 years before earliest class)
- School-average ACT/SAT and years of universal testing (where testing isn't universal, record that and use state test proficiency from EDFacts instead)
- Race shares and total enrollment (CCD preferred, if not possible, note it and use state files)
- School type (to drop special-ed, virtual, alternative); student/teacher ratio inputs
- Deneault's weights: average pre-period total students ÷ number of grades taught
- Deneault's own dose definition (Louisiana: 1 − average FCR over 2015–16, with 2017 as the reference), so the Louisiana replication is exact

## Needed for the added controls and heterogeneity
- Free/reduced-price lunch, direct certification counts, and Community Eligibility Provision status by year (FRL breaks under CEP)
- Income: NCES EDGE School Neighborhood Poverty Estimates; ACS-ED district profiles (median income, parental education, foreign-born and non-citizen households)
- Counselors per student and English learner share (Civil Rights Data Collection; note which years)
- Title I, locale, charter, magnet, % male, grade-12 size (CCD)
- Distance to the nearest public 2-year and 4-year college (EDGE geocodes + IPEDS)
- FSA submissions as well as completions (for completions ÷ submissions); filing timing within the cycle where FSA releases allow it
- 2-year vs 4-year and in-state vs out-of-state enrollment, where the state splits them

## Needed for the pooling model (state-level predictors)
- Policy type: graduation requirement, offer/confirm or tracking only, grant schools only (CO), or support duty (MD)
- Who the mandate binds (students vs. districts vs. specific schools)
- Who can grant a waiver (parent/adult student only, or counselor/principal/superintendent too) and whether the diploma is withheld
- State agency role (forms, reporting, monitoring) vs. what is left to districts
- Accompanying supports (outreach, counseling, completion events) and concurrent aid or free-college programs
- Whether the state has its own alternative aid application for undocumented students
- All with a statute or state agency source
- Whether the first covered class falls in the COVID years (classes of 2020–21) or the FAFSA rollout year (class of 2024)

## Needed for enforcement and undocumented-student analyses
- Waiver/opt-out counts by district or school, where published
- State compliance reports or district implementation records
- Counts of the state alternative aid application by high school (e.g., CSAC "Race to Submit" for CADAA in California; TASFA, Illinois Alternative Application and others if available)
- School proxies for immigrant communities: English learner share, % Hispanic, ACS-ED non-citizen share; county estimates of the unauthorized population [CHECK coverage]

## Never-adopting states (robustness only)
Used for the triple difference against never-adopting states (D_s × Post × Adopt), mainly for the 2025 adopters whose reference class is the FAFSA rollout year, for placebo runs, and for the cross-state first-stage check.
- List of states with no mandate passed or implemented through the last class in the sample; exclude states that passed a law but had not implemented it (anticipation risk), and flag edge cases (e.g., Kansas: passed and repealed before taking effect)
- Exclude CO and MD, which have related policies
- FSA FAFSA completion by high school for every class used by any adopting state
- School-level college enrollment for at least some comparison states, if a reduced-form triple difference is wanted; otherwise the triple difference covers the first stage only

## Federal (same for all states)
- FSA FAFSA completion by high school (completed/submitted as of June; from class of 2015; counts <5 suppressed; name+city only)
- NCES CCD: NCES ID, school type, enrollment by grade and race, FRPL, direct certification, CEP, locale, Title I, teacher FTE
- EDFacts ACGR and state test proficiency
- NCES EDGE (neighborhood poverty, ACS-ED, geocodes), CRDC, IPEDS
- FSA data for never-adopting states

## Timing to record per state
- Which classes form the dose window, which is the reference class, and which are post-mandate (first stage and enrollment separately)
- Where the class of 2017 (first class under the October 2016 FAFSA launch and prior-prior year income), the classes of 2020–21 (COVID), and the class of 2024 (FAFSA rollout) fall relative to those
- CT and PA (class of 2027): pre-period only; record when post-mandate FSA and enrollment data are expected, and check the class of 2026 for anticipation

## Cross-state requirements (for pooling)
- Enrollment definitions recorded in docs/state-metadata.md: source (Clearinghouse vs state records), window (fall vs 12/16-month), in-state vs all institutions, denominator, suppression rules
- Dose on the same 0–1 scale in every state, so β is comparable
- The first covered class (e = 0) available in every pooled state, for each outcome
- Enough states per policy type to estimate the policy-type covariate (or a decision to pool graduation-requirement states only)
- Rules for the dose window, post-window, controls and pooling structure recorded in DECISIONS.md before viewing post-period outcomes
