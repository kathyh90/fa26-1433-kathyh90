# Write a plain-language summary of the pooling results, with every number read from the outputs.
#
# Inputs:  output/tables/pooling_hyper.csv, pooling_states.csv, pooling_loo.csv (12_aggregation.R),
#          output/tables/pooling_baggr_check.csv (13_baggr_check.R; optional)
# Output:  output/pooling_summary.md     (Markdown)
#          output/pooling_summary.html   (same content; forest plot embedded; math rendered by KaTeX)
#
# Run from the repository root:  Rscript code/14_pooling_report.R

script_dir <- function() {
  # Folder of this script when run with Rscript; fall back to code/ under the working directory.
  arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(arg)) dirname(normalizePath(sub("^--file=", "", arg))) else file.path(getwd(), "code")
}
OUTPUT <- file.path(dirname(script_dir()), "output")
TABLES <- file.path(OUTPUT, "tables")
hyper  <- read.csv(file.path(TABLES, "pooling_hyper.csv"))
states <- read.csv(file.path(TABLES, "pooling_states.csv"))
loo    <- read.csv(file.path(TABLES, "pooling_loo.csv"))
check_path <- file.path(TABLES, "pooling_baggr_check.csv")
OUTCOMES <- c(fafsa_completion = "FAFSA completion", college_enrollment = "College enrollment")

# ---- Helpers -------------------------------------------------------------------------------
f3 <- function(x) formatC(x, format = "f", digits = 3)
ci <- function(r) sprintf("%s [%s, %s]", f3(r$mean), f3(r$q025), f3(r$q975))

md_table <- function(df) {
  # Data frame -> Markdown table lines.
  c(paste0("| ", paste(names(df), collapse = " | "), " |"),
    paste0("|", paste(rep("---", ncol(df)), collapse = "|"), "|"),
    apply(df, 1, function(r) paste0("| ", paste(r, collapse = " | "), " |")))
}

MAIN_INPUT <- "common_window"   # as in 12_aggregation.R

par_ci <- function(o, m, pr, p, input = MAIN_INPUT) {
  # "mean [q025, q975]" for one input spec x outcome x model x prior x parameter, or a dash if absent.
  r <- hyper[hyper$input_spec == input & hyper$outcome == o & hyper$model == m & hyper$prior == pr & hyper$parameter == p, ]
  if (nrow(r)) ci(r) else "-"
}

metric <- function(o, m, col) states[states$outcome == o & states$model == m, col][1]

reading <- function(x) if (x < 0.5) "mostly real differences" else "mostly sampling noise"

# ---- Sections ------------------------------------------------------------------------------
# Text uses LaTeX math ($...$ inline, $$...$$ on its own line): GitHub and VS Code render it in the
# Markdown file, KaTeX in the HTML file. R raw strings r"---(...)---" keep the backslashes readable.

results_table <- function() {
  rows <- expand.grid(model = c("no_covariate", "covariate"), o = names(OUTCOMES), stringsAsFactors = FALSE)
  out <- data.frame(
    Outcome = OUTCOMES[rows$o], Model = sub("_", " ", rows$model),
    States = as.character(sapply(rows$o, function(o) length(unique(states$state[states$outcome == o])))),
    mu = mapply(par_ci, rows$o, rows$model, "main", "mu"),
    sigma = mapply(par_ci, rows$o, rows$model, "main", "sigma_beta"),
    delta = mapply(par_ci, rows$o, rows$model, "main", "delta"), row.names = NULL)
  names(out)[4:6] <- c(r"---($\mu$ (average effect))---", r"---($\sigma_\beta$ (SD across states))---",
                       r"---($\delta$ (no-diploma difference))---")
  md_table(out)
}

prediction_table <- function() {
  rows <- expand.grid(model = c("no_covariate", "covariate"), o = names(OUTCOMES), stringsAsFactors = FALSE)
  md_table(data.frame(
    Outcome = OUTCOMES[rows$o], Model = sub("_", " ", rows$model),
    `New diploma-withheld state` = mapply(par_ci, rows$o, rows$model, "main", "new_state"),
    `Connecticut` = mapply(par_ci, rows$o, rows$model, "main", "predict_CT"),
    `Pennsylvania` = mapply(par_ci, rows$o, rows$model, "main", "predict_PA"),
    check.names = FALSE, row.names = NULL))
}

state_table <- function(o) {
  d <- states[states$outcome == o & states$model == "no_covariate", ]
  d <- d[order(-d$beta), ]
  out <- data.frame(State = d$state, est = sprintf("%s (%s)", f3(d$beta), f3(d$se)),
                    pooled = sprintf("%s [%s, %s]", f3(d$beta_k_mean), f3(d$beta_k_q025), f3(d$beta_k_q975)),
                    omega = formatC(d$omega_k, format = "f", digits = 2))
  names(out)[2:4] <- c(r"---(Own estimate $\hat\beta_k$ (SE))---", r"---(Pooled effect $\beta_k$ [95%])---", r"---($\omega_k$)---")
  md_table(out)
}

metric_table <- function() {
  rows <- unique(states[, c("outcome", "model", "omega_bar", "lambda_gp")])
  avg <- (rows$omega_bar + rows$lambda_gp) / 2
  out <- data.frame(Outcome = OUTCOMES[rows$outcome], Model = sub("_", " ", rows$model),
                    ob = f3(rows$omega_bar), lg = f3(rows$lambda_gp),
                    Average = f3(avg), Reading = sapply(avg, reading), row.names = NULL)
  names(out)[3:4] <- c(r"---($\bar\omega$)---", r"---($\lambda_\beta$)---")
  md_table(out)
}

sensitivity_table <- function() {
  priors <- c(main = "Main (weakly informative)",
              flat_uniform = r"---(Flat $\mu$, $\sigma_\beta \sim \mathrm{Uniform}(0, 1)$)---",
              half_cauchy_05 = r"---($\sigma_\beta \sim \text{Half-Cauchy}(0, 0.05)$)---")
  rows <- expand.grid(pr = names(priors), o = names(OUTCOMES), stringsAsFactors = FALSE)
  out <- data.frame(Outcome = OUTCOMES[rows$o], Prior = priors[rows$pr],
                    mu = mapply(par_ci, rows$o, "no_covariate", rows$pr, "mu"),
                    sigma = mapply(par_ci, rows$o, "no_covariate", rows$pr, "sigma_beta"),
                    `New state` = mapply(par_ci, rows$o, "no_covariate", rows$pr, "new_state"),
                    check.names = FALSE, row.names = NULL)
  names(out)[3:4] <- c(r"---($\mu$)---", r"---($\sigma_\beta$)---")
  md_table(out)
}

window_table <- function() {
  # Each pooled state's classes under the common window (main) and Deneault's window (sensitivity).
  read <- function(f, o) { d <- read.csv(file.path(TABLES, f)); d$outcome <- o
                           d[d$spec %in% c(MAIN_INPUT, "main"), c("state", "outcome", "spec", "classes", "n_schools")] }
  d <- rbind(read("first_stage_by_state.csv", "fafsa_completion"), read("reduced_form_by_state.csv", "college_enrollment"))
  w <- reshape(d, idvar = c("state", "outcome"), timevar = "spec", direction = "wide")
  w <- w[order(match(w$outcome, names(OUTCOMES)), w$state), ]
  cell <- function(spec) sprintf("%s (%s schools)", w[[paste0("classes.", spec)]], w[[paste0("n_schools.", spec)]])
  md_table(data.frame(Outcome = OUTCOMES[w$outcome], State = w$state, `Common window (main)` = cell(MAIN_INPUT),
                      `Deneault window` = cell("main"), check.names = FALSE, row.names = NULL))
}

window_sensitivity_table <- function() {
  # Pooled mu and sigma_beta under the two windows (main prior, no covariate).
  rows <- expand.grid(input = c(MAIN_INPUT, "main"), o = names(OUTCOMES), stringsAsFactors = FALSE)
  out <- data.frame(Outcome = OUTCOMES[rows$o],
                    Window = ifelse(rows$input == MAIN_INPUT, "Common, e = -3 to 0 (main)", "Deneault, e = -4 to +1 where available"),
                    mu = mapply(par_ci, rows$o, "no_covariate", "main", "mu", rows$input),
                    sigma = mapply(par_ci, rows$o, "no_covariate", "main", "sigma_beta", rows$input), row.names = NULL)
  names(out)[3:4] <- c(r"---($\mu$)---", r"---($\sigma_\beta$)---")
  md_table(out)
}

loo_lines <- function() {
  out <- loo[!loo$inside_95, ]
  if (!nrow(out)) return("Every state's estimate lies inside the 95% predictive interval from the other states.")
  c(sprintf("%d of %d state estimates fall outside the 95%% predictive interval built from the other states:",
            nrow(out), nrow(loo)), "",
    sprintf(r"---(- %s, %s: $\hat\beta_k$ = %s; the other states predict %s [%s, %s].)---", out$dropped,
            OUTCOMES[out$outcome], f3(out$beta), f3(out$pred_mean), f3(out$pred_q025), f3(out$pred_q975)),
    "", "These states are unusual relative to the rest, so check their designs and data before reading their shrunk effects.")
}

baggr_lines <- function() {
  if (!file.exists(check_path)) return("Not run (baggr not installed). See `code/13_baggr_check.R`.")
  c <- read.csv(check_path)
  sprintf(paste("baggr 0.8.2 (Wiecek and Meager; Stan MCMC, 4 chains x 40,000 iterations) fits the same model",
                "with the same main priors. %d of %d parameters match (means within 0.1 and 95%% bounds within",
                "0.2 posterior SDs of the exact result); largest R-hat %.3f. baggr was archived on CRAN on",
                "2026-11-01, so the main code does not depend on it."), sum(c$match), nrow(c), max(c$max_rhat))
}

covariate_line <- function() {
  # How lambda_beta changes once the diploma indicator explains part of the spread.
  up <- sapply(names(OUTCOMES), function(o) metric(o, "covariate", "lambda_gp") > metric(o, "no_covariate", "lambda_gp"))
  if (all(up)) r"---(In the covariate model, the diploma indicator explains part of the cross-state spread, so the remaining differences look relatively more like noise ($\lambda_\beta$ rises for both outcomes).)---"
  else r"---(Adding the diploma indicator does not consistently change $\lambda_\beta$ across outcomes.)---"
}

# ---- Report --------------------------------------------------------------------------------
fs_ob <- metric("fafsa_completion", "no_covariate", "omega_bar")
fs_lg <- metric("fafsa_completion", "no_covariate", "lambda_gp")
en_ob <- metric("college_enrollment", "no_covariate", "omega_bar")
en_lg <- metric("college_enrollment", "no_covariate", "lambda_gp")

report <- c(
"# Pooling the state estimates: summary",
"",
"*Generated by `code/14_pooling_report.R` from the outputs of `code/12_aggregation.R` and `code/13_baggr_check.R`. Do not edit by hand.*",
"",
"## 1. What the pooling does",
"",
r"---(Each state has its own estimate of the mandate's effect, $\hat\beta_k$: the dose $\times$ post coefficient from Deneault's specification, with a school-clustered SE $\hat s_k$. There is one for the first stage (FAFSA completion) and one for the reduced form (college enrollment). A Bayesian hierarchical model (Rubin 1981; Gelman et al. 2013, ch. 5; Meager 2019) combines them. It asks two questions: what is the average effect across states, and how much do the true effects differ once sampling noise is removed? It is baggr's "Rubin" summary-data model with partial pooling.)---",
"",
"## 2. Model and notation",
"",
r"---(For each outcome, with states $k = 1, \dots, K$:)---",
"",
r"---($$\hat\beta_k \sim N\left(\beta_k,\ \hat s_k^2\right), \qquad \beta_k \sim N\left(\mu + \delta Z_k,\ \sigma_\beta^2\right)$$)---",
"",
"- **Data level:** each estimate is the state's true effect plus noise of known size.",
"- **Population level:** the true effects come from a common distribution.",
"",
md_table(data.frame(
  Concept = c("State's estimate and SE", "State's true effect", "Average effect across states (hypermean)",
              "SD of true effects (hyper-SD)", "Covariate coefficient", "Covariate"),
  Here = c(r"---($\hat\beta_k$, $\hat s_k$ (`beta`, `se`))---", r"---($\beta_k$ (`beta_k_*`))---", r"---($\mu$ (`mu`))---",
           r"---($\sigma_\beta$ (`sigma_beta`))---", r"---($\delta$ (`delta`))---", r"---($Z_k$ = `no_diploma`)---"),
  `baggr vignette` = c(r"---($\hat\tau_k$, $\hat{se}_k$)---", r"---($\tau_k$)---", r"---($\tau$)---",
                       r"---($\sigma_\tau$)---", r"---($\beta$)---", "covariates"),
  check.names = FALSE)),
"",
r"---(The covariate is a single indicator, $Z_k$ = `no_diploma` = 1 when the mandate does not withhold the diploma (California and New York; Pennsylvania for prediction) and 0 when it does (every other state). In the covariate model, $\mu$ is therefore the average effect in diploma-withheld states and $\delta$ is how much the effect differs in no-diploma states. Within the pooled states this split is the same as graduation requirement vs. LEA requirement. For enrollment, the no-diploma group is California alone.)---",
"",
"## 3. Estimation window",
"",
r"---(Each state's $\hat\beta_k$ compares its post-mandate class with the average of its pre-period classes in the window. The pre-period includes the dose classes ($e = -3, -2$), which dip mechanically because the dose is built from completion in exactly those classes. So the pre-period baseline must be the same in every state, or the window itself creates differences between states. Louisiana's FSA data start at $e = -3$, so the common window is **$e = -3$ to $0$ in every state**: dose classes $-3$ and $-2$, reference class $-1$, and the first covered class $e = 0$ as the post period. Deneault's window ($e = -4$ to $+1$ where available), used for the state headline results, is pooled as a sensitivity check (section 9).)---",
"",
window_table(),
"",
"Balance is required only over the window's classes, so the common window keeps slightly more schools.",
"",
"## 4. What pooling does to each state",
"",
r"---(Given $\mu$ and $\sigma_\beta$, each state's pooled effect is a weighted mix of the cross-state center and its own estimate (spec eq. 6):)---",
"",
r"---($$\mathbb{E}\left[\beta_k \mid \hat\beta_k, \mu, \sigma_\beta\right] = \omega_k\,(\mu + \delta Z_k) + (1 - \omega_k)\,\hat\beta_k, \qquad \omega_k = \frac{\hat s_k^2}{\sigma_\beta^2 + \hat s_k^2}$$)---",
"",
r"---(- A precise state (small $\hat s_k$) has $\omega_k$ near 0 and keeps its own estimate.)---",
r"---(- A noisy state has $\omega_k$ near 1 and is pulled toward the center, because its own estimate says little.)---",
r"---(- $\sigma_\beta$ is learned from the data. If the estimates differ more than their SEs can explain, $\sigma_\beta$ is large and every state keeps more of its own estimate.)---",
"",
r"---($\mu$ is a precision-weighted average of the states with weights $1 / (\hat s_k^2 + \sigma_\beta^2)$. It lies between the plain average (no pooling) and the $1/\hat s_k^2$-weighted average (full pooling, which assumes one common effect and lets the most precise states dominate). Because $\sigma_\beta$ is uncertain, the model averages over it, so every interval carries that uncertainty. Pulling noisy estimates toward the center makes the state estimates more accurate on average and keeps a noisy outlier from being over-read.)---",
"",
"## 5. Priors",
"",
"The priors are weakly informative and set on the 0-1 dose scale, with every scale halved for enrollment:",
"",
md_table(data.frame(
  Parameter = c(r"---($\mu$)---", r"---($\delta$)---", r"---($\sigma_\beta$)---"),
  `FAFSA completion` = c(r"---($N(0, 1)$)---", r"---($N(0, 0.5^2)$)---", r"---($\text{Half-Normal}(0, 0.5)$)---"),
  `95% of prior mass` = c("[-1.96, 1.96]", "[-0.98, 0.98]", "below 0.98 (median 0.34)"),
  `College enrollment` = c(r"---($N(0, 0.5^2)$)---", r"---($N(0, 0.25^2)$)---", r"---($\text{Half-Normal}(0, 0.25)$)---"),
  `95% of prior mass ` = c("[-0.98, 0.98]", "[-0.49, 0.49]", "below 0.49 (median 0.17)"),
  check.names = FALSE)),
"",
r"---(- **Not hard limits.** The 95% ranges are where the prior puts most of its weight; values outside are allowed, only considered less likely. The only hard limit is $\sigma_\beta \ge 0$ (the computation also caps $\sigma_\beta$ at 1, where the posterior has no mass).)---",
r"---(- **Why wider than 1.** $\beta_k$ is a slope per unit of dose: the effect for a dose-1 school relative to a dose-0 school. No state spans the full 0-1 dose range (about 0.1 to 0.7-0.9), so $\beta_k$ extrapolates and can exceed 1 in principle, or be negative. A weakly informative prior is meant to be wider than the plausible range, so it gives realistic values nearly equal weight ($N(0, 1)$ at 0.4 is 92% of its peak) and only rules out impossible values.)---",
r"---(- **Half-Normal.** A normal distribution centered at 0 and folded at zero, so only values $\ge 0$ are allowed, which suits a standard deviation. It is highest at 0 (mildly favoring similar states), declines smoothly, and has no arbitrary upper bound. Its scale is the SD of the normal before folding.)---",
"- **Why enrollment is halved.** The enrollment effect is roughly the FAFSA effect times the share of extra completers who enroll, which is well below 1. Halving keeps the two sets of priors equally weak relative to the size of each outcome's effects. A fixed factor is used rather than the observed ratio so the data are not used twice.",
r"---(- **Why these and not flat priors.** They are proper, so they can be stated, checked and reproduced exactly in baggr. They are on each outcome's scale, and keep $\delta$ in a plausible range when one state carries it. The old flat/uniform priors are kept as a sensitivity check (section 9).)---",
"",
"## 6. Main results",
"",
"Posterior mean [95% interval], main priors:",
"",
results_table(),
"",
sprintf(r"---(- **FAFSA completion:** across states, the mandate raises completion by $\mu$ = %s per unit of dose. True effects differ across states with $\sigma_\beta$ = %s, a large spread relative to the mean.)---",
        par_ci("fafsa_completion", "no_covariate", "main", "mu"), par_ci("fafsa_completion", "no_covariate", "main", "sigma_beta")),
sprintf(r"---(- **College enrollment:** the average effect is $\mu$ = %s; the spread across states, $\sigma_\beta$ = %s, is poorly pinned down with %d states.)---",
        par_ci("college_enrollment", "no_covariate", "main", "mu"), par_ci("college_enrollment", "no_covariate", "main", "sigma_beta"),
        length(unique(states$state[states$outcome == "college_enrollment"]))),
sprintf(r"---(- **Diploma consequence:** in no-diploma states the FAFSA effect differs by $\delta$ = %s; the interval includes 0. For enrollment, $\delta$ rests on California alone and is uninformative.)---",
        par_ci("fafsa_completion", "covariate", "main", "delta")),
"",
r"---(Predicted effects (posterior predictive: draw $\mu$, $\delta$ and $\sigma_\beta$, then a new state's effect from $N(\mu + \delta Z, \sigma_\beta^2)$) for a new state and for the states without post-mandate data yet:)---",
"",
prediction_table(),
"",
r"---(Predictions are wide because they include the spread across states ($\sigma_\beta$), not only uncertainty about the average.)---",
"",
"## 7. State-level pooled effects (model without the covariate)",
"",
"### FAFSA completion", "", state_table("fafsa_completion"), "",
"### College enrollment", "", state_table("college_enrollment"), "",
r"---(The forest plot shows the **covariate model** (the paper's main pooling model): each state is pulled toward its own group's center, $\mu$ for diploma-withheld states (blue) and $\mu + \delta$ for no-diploma states (orange). The tables above are the model without the covariate.)---",
"",
"![Forest plot (covariate model)](figures/pooling_forest.png)",
"",
"## 8. Pooling metrics: how much of the cross-state variation is noise",
"",
r"---(**Average pooling factor**, evaluated at the posterior mean of $\sigma_\beta^2$ (as Meager does). Each state counts equally:)---",
"",
r"---($$\bar\omega = \frac{1}{K} \sum_{k=1}^{K} \omega_k = \frac{1}{K} \sum_{k=1}^{K} \frac{\hat s_k^2}{\sigma_\beta^2 + \hat s_k^2}$$)---",
"",
r"---(**Generalized pooling factor** (Gelman and Pardoe 2006; Meager eq. 8), with $\varepsilon_k = \beta_k - (\mu + \delta Z_k)$ from posterior draws. Unlike $\bar\omega$, it carries the uncertainty in $\sigma_\beta$:)---",
"",
r"---($$\lambda_\beta = 1 - \frac{\frac{1}{K-1} \sum_{k=1}^{K} \left(\mathbb{E}_{\text{post}}[\varepsilon_k] - \overline{\mathbb{E}_{\text{post}}[\varepsilon]}\right)^2}{\mathbb{E}_{\text{post}}\left[\frac{1}{K-1} \sum_{k=1}^{K} (\varepsilon_k - \bar\varepsilon)^2\right]}$$)---",
"",
"Values above 0.5 mean states look different mostly by chance; values near 0 mean the differences are real. Meager's summary averages the metrics.",
"",
metric_table(),
"",
sprintf(r"---(FAFSA completion: %s ($\bar\omega$ = %s, $\lambda_\beta$ = %s). College enrollment: the metrics disagree ($\bar\omega$ = %s, $\lambda_\beta$ = %s), because $\sigma_\beta$ is poorly pinned down with few states; their average, %s, points to %s.)---",
        reading((fs_ob + fs_lg) / 2), f3(fs_ob), f3(fs_lg), f3(en_ob), f3(en_lg), f3((en_ob + en_lg) / 2), reading((en_ob + en_lg) / 2)),
covariate_line(),
"",
r"---(An earlier version reported a single ratio of averages, $\overline{\hat s^2} / (\overline{\hat s^2} + \mathbb{E}[\sigma_\beta^2])$ (baggr's overall pooling). Because the noisiest states dominate the average of squared SEs, that ratio is always at least $\bar\omega$; the difference is largest for enrollment, where SEs vary most.)---",
"",
"## 9. Sensitivity (model without the covariate)",
"",
"**Window.** Pooled estimates under the common window (main) and Deneault's window, where some states include $e = -4$ and $e = +1$ and others do not:",
"",
window_sensitivity_table(),
"",
r"---(With windows that differ across states, part of the spread between states comes from the windows themselves, so $\sigma_\beta$ is larger; the common window removes that. The common window's baseline consists mostly of the dose classes, whose mechanical dip raises every state's $\hat\beta_k$, so $\mu$ is higher. This dip is the open pre-trend problem: it now affects every state in the same way, but the level of $\mu$ should be read with that caveat.)---",
"",
"**Priors.**",
"",
sensitivity_table(),
"",
r"---(The average effect does not depend on the prior. Only the skeptical half-Cauchy prior, which favors similar states, moves $\sigma_\beta$ (down by about 10-15%) and narrows the predictions. Each posterior interval is a small fraction of its prior range: the data, not the priors, drive the results.)---",
"",
"## 10. Leave-one-state-out",
"",
loo_lines(),
"",
"## 11. Cross-check with baggr",
"",
baggr_lines(),
"",
"## 12. Computation",
"",
r"---(`code/12_aggregation.R` computes the posterior exactly in base R: $\sigma_\beta$ is drawn from its marginal posterior on a 5,000-point grid, then $\mu$, $\delta$ and $\beta_k$ from their normal conditionals (Gelman et al. 2013, ch. 5). This works because the model has a single variance parameter. A model with several (for example, pooling FAFSA completion and enrollment jointly) would need MCMC through baggr or Stan.)---",
"",
"## 13. Caveats",
"",
"- The state estimates inherit the open pre-trend problem in the event studies (DECISIONS 2026-11-11). The dose classes make up two-thirds of the common window's baseline, so the mechanical dip likely raises every state's estimate and the pooled mean; the common window makes this bias the same across states, not zero.",
r"---(- The enrollment outcome is defined differently across states (timing window, in-state only, data source), so $\sigma_\beta$ for enrollment mixes real heterogeneity with definition differences.)---",
"- State SEs are treated as known, which is standard for summary-data pooling.",
"- Maryland is excluded (no FAFSA requirement). Connecticut and Pennsylvania have no post-mandate data yet; their predictions are an out-of-sample test to check later.",
"- The connection to Meager (2019) is described, not quoted; the model is matched to her equations as summarized in the project spec.",
"",
"## Reproduce",
"",
"```bash",
"Rscript code/12_aggregation.R    # exact pooling (base R)",
"Rscript code/13_baggr_check.R    # optional cross-check (needs baggr 0.8.2; see README)",
"Rscript code/14_pooling_report.R # this summary",
"```")

# ---- HTML version ----------------------------------------------------------------------------
# Base R converter for the Markdown subset used above (no pandoc needed): headings, paragraphs,
# bullet lists, tables, fenced code, one image, display math ($$...$$ lines), **bold**, *italic*, `code`.
# Math is left as LaTeX for KaTeX to render in the browser (needs internet; offline, the LaTeX shows as text).

base64_file <- function(path) {
  # Base64-encode a file so the HTML embeds the figure and works on its own.
  r <- as.integer(readBin(path, "raw", file.size(path)))
  pad <- (3 - length(r) %% 3) %% 3
  n <- colSums(matrix(c(r, integer(pad)), nrow = 3) * c(65536L, 256L, 1L))
  idx <- rbind(n %/% 262144L, (n %/% 4096L) %% 64L, (n %/% 64L) %% 64L, n %% 64L)
  out <- strsplit("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", "")[[1]][idx + 1]
  if (pad) out[length(out) - seq_len(pad) + 1] <- "="
  paste(out, collapse = "")
}

esc <- function(x) {
  # Escape the HTML special characters.
  x <- gsub("&", "&amp;", x, fixed = TRUE); x <- gsub("<", "&lt;", x, fixed = TRUE); gsub(">", "&gt;", x, fixed = TRUE)
}

inline <- function(x) {
  # Escape HTML, then convert inline Markdown (inline $...$ math is left for KaTeX).
  x <- esc(x)
  x <- gsub("`([^`]+)`", "<code>\\1</code>", x)
  x <- gsub("\\*\\*([^*]+)\\*\\*", "<strong>\\1</strong>", x)
  gsub("\\*([^* ][^*]*[^* ])\\*", "<em>\\1</em>", x)   # *text*, not the spaced * of a product
}

table_html <- function(rows) {
  # Markdown table lines -> HTML table (first row header, second row the separator).
  cells <- lapply(rows, function(l) trimws(strsplit(sub("^\\|(.*)\\|$", "\\1", l), "|", fixed = TRUE)[[1]]))
  tr <- function(v, tag) paste0("<tr>", paste0("<", tag, ">", inline(v), "</", tag, ">", collapse = ""), "</tr>")
  c('<div class="table-wrap"><table>', paste0("<thead>", tr(cells[[1]], "th"), "</thead><tbody>"),
    vapply(cells[-(1:2)], tr, "", tag = "td"), "</tbody></table></div>")
}

md_to_html <- function(lines) {
  # Walk the Markdown lines block by block.
  out <- character(); i <- 1
  while (i <= length(lines)) {
    l <- lines[i]
    if (l == "") { i <- i + 1; next }
    if (startsWith(l, "```")) {                                   # fenced code
      j <- i + 1; while (!startsWith(lines[j], "```")) j <- j + 1
      out <- c(out, paste0("<pre><code>", paste(inline(lines[(i + 1):(j - 1)]), collapse = "\n"), "</code></pre>"))
      i <- j + 1; next
    }
    if (startsWith(l, "$$")) {                                    # display math, one line
      out <- c(out, paste0('<div class="math-display">', esc(l), "</div>")); i <- i + 1; next
    }
    if (grepl("^#{1,3} ", l)) {                                   # headings
      h <- nchar(sub(" .*", "", l))
      out <- c(out, sprintf("<h%d>%s</h%d>", h, inline(sub("^#+ ", "", l)), h)); i <- i + 1; next
    }
    if (grepl("^!\\[", l)) {                                      # image, embedded
      src <- sub(".*\\((.*)\\)$", "\\1", l); alt <- sub("^!\\[(.*)\\].*", "\\1", l)
      out <- c(out, sprintf('<figure><img alt="%s" src="data:image/png;base64,%s"></figure>',
                            alt, base64_file(file.path(OUTPUT, src))))
      i <- i + 1; next
    }
    kind <- function(x) if (startsWith(x, "|")) "table" else if (startsWith(x, "- ")) "list" else "text"
    j <- i; while (j <= length(lines) && lines[j] != "" && !startsWith(lines[j], "```") &&
                   !grepl("^(#{1,3} |!\\[|\\$\\$)", lines[j]) && kind(lines[j]) == kind(l)) j <- j + 1
    block <- lines[i:(j - 1)]
    if (startsWith(l, "|")) out <- c(out, table_html(block))     # table
    else if (startsWith(l, "- ")) out <- c(out, "<ul>", paste0("<li>", inline(sub("^- ", "", block)), "</li>"), "</ul>")
    else out <- c(out, paste0("<p>", paste(inline(block), collapse = "<br>"), "</p>"))
    i <- j
  }
  out
}

CSS <- "
:root { --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0; --soft: #f6f8fa; --accent: #0969da; }
@media (prefers-color-scheme: dark) { :root:not([data-theme='light']) {
  --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --line: #3d444d; --soft: #151b23; --accent: #4493f8; } }
:root[data-theme='dark'] { --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --line: #3d444d; --soft: #151b23; --accent: #4493f8; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }
main { max-width: 900px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 1.9rem; line-height: 1.25; margin: 0 0 8px; }
h2 { font-size: 1.35rem; margin: 40px 0 12px; padding-bottom: 6px; border-bottom: 1px solid var(--line); }
h3 { font-size: 1.1rem; margin: 24px 0 8px; }
p, li { color: var(--fg); } em { color: var(--muted); }
code { font: 0.88em ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--soft);
  padding: 1px 5px; border-radius: 4px; }
pre { background: var(--soft); border: 1px solid var(--line); border-radius: 6px; padding: 12px 14px; overflow-x: auto; }
pre code { background: none; padding: 0; }
.table-wrap { overflow-x: auto; margin: 12px 0 20px; }
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; font-variant-numeric: tabular-nums; }
th, td { border: 1px solid var(--line); padding: 6px 10px; text-align: left; vertical-align: top; }
th { background: var(--soft); font-weight: 600; }
tbody tr:nth-child(even) td { background: color-mix(in srgb, var(--soft) 60%, transparent); }
.math-display { overflow-x: auto; overflow-y: hidden; margin: 16px 0; padding: 4px 0; }
.katex { font-size: 1.05em; }
figure { margin: 16px 0; } img { max-width: 100%; height: auto; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
"

KATEX <- c(  # KaTeX 0.16.9 from cdnjs: renders $...$ and $$...$$ after the page loads
  '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">',
  '<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>',
  paste0('<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js" ',
         'onload="renderMathInElement(document.body, {delimiters: [{left: \'$$\', right: \'$$\', display: true}, ',
         '{left: \'$\', right: \'$\', display: false}], throwOnError: false});"></script>'))

write_html <- function(lines, path) {
  html <- c("<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Pooling Results Summary</title>", "<style>", CSS, "</style>", KATEX, "</head>",
            "<body>", "<main>", md_to_html(lines), "</main>", "</body>", "</html>")
  writeLines(html, path)
}

writeLines(report, file.path(OUTPUT, "pooling_summary.md"))
write_html(report, file.path(OUTPUT, "pooling_summary.html"))
message("Wrote output/pooling_summary.md and output/pooling_summary.html")
