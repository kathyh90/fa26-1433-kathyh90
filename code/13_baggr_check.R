# Cross-check 12_aggregation.R against baggr (Wiecek & Meager), which fits the same Rubin model by MCMC (Stan).
#
# Fits baggr's "rubin" model to the same inputs with the main priors of 12_aggregation.R, which
# baggr expresses exactly (scale s = 1 for FAFSA completion, 0.5 for enrollment):
#   prior_hypermean = normal(0, s), prior_beta = normal(0, 0.5 s), prior_hypersd = normal(0, 0.5 s)
#   (baggr's hyper-SD is constrained >= 0, so the last is Half-Normal(0, 0.5 s)).
# baggr's names differ: its hypermean is `tau` (our mu), its hyper-SD `sigma_tau` (our sigma_beta),
# its covariate coefficient `beta` (our delta). The sensitivity priors are not checked
# (baggr's prior_hypersd allows only normal or uniform, and its hypermean prior cannot be flat).
#
# Input:  output/tables/pooling_hyper.csv (from 12_aggregation.R), plus its inputs
# Output: output/tables/pooling_baggr_check.csv   one row per outcome x model x parameter:
#         exact (12_aggregation.R) vs. baggr mean and 95% interval, and `match`
#         (|mean difference| < 0.1 posterior SD and both 95% bounds within 0.2 posterior SD).
#         40,000 iterations per chain: at 10,000, MCMC noise in the 97.5% tail of sigma_beta exceeded the tolerance.
#
# baggr was archived on CRAN on 2026-11-01. Install the last release (0.8.2) from the archive:
#   install.packages(c("rstan", "rstantools", "StanHeaders", "RcppParallel", "RcppEigen",
#                      "bayesplot", "forestplot", "ggplotify", "ggrepel", "gridExtra"))
#   install.packages("https://cran.r-project.org/src/contrib/Archive/baggr/baggr_0.8.2.tar.gz",
#                    repos = NULL, type = "source")
# Run from the repository root:  Rscript code/13_baggr_check.R

suppressPackageStartupMessages(library(baggr))
set.seed(20261113)

script_dir <- function() {
  # Folder of this script when run with Rscript; fall back to code/ under the working directory.
  arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(arg)) dirname(normalizePath(sub("^--file=", "", arg))) else file.path(getwd(), "code")
}
ROOT   <- dirname(script_dir())
TABLES <- file.path(ROOT, "output", "tables")
POLICY <- file.path(ROOT, "data", "policy", "state_mandates.csv")
HOLDOUT <- c("CT", "PA")
INPUT   <- "common_window"   # the main pooled input of 12_aggregation.R (e = -3 ... 0 in every state)

OUTCOME_SCALE <- c(fafsa_completion = 1, college_enrollment = 0.5)   # as in 12_aggregation.R

# Same inputs as 12_aggregation.R's main analysis: common-window beta and se per state, no_diploma covariate.
read_estimates <- function() {
  fs <- read.csv(file.path(TABLES, "first_stage_by_state.csv"))
  rf <- read.csv(file.path(TABLES, "reduced_form_by_state.csv"))
  est <- rbind(transform(fs[fs$spec == INPUT, c("state", "beta", "se")], outcome = "fafsa_completion"),
               transform(rf[rf$spec == INPUT, c("state", "beta", "se")], outcome = "college_enrollment"))
  merge(est, policy_covariate(), by = "state")
}

policy_covariate <- function() {
  m <- read.csv(POLICY)
  data.frame(state = m$state, no_diploma = as.integer(m$graduation_consequence == "none"))
}

summarise <- function(draws) {
  c(mean = mean(draws), sd = sd(draws), q025 = unname(quantile(draws, 0.025)),
    q975 = unname(quantile(draws, 0.975)))
}

fit_baggr <- function(d, covariate, s) {
  # baggr Rubin model on one outcome with prior scale s; baggr requires the columns tau (state estimate), se, group.
  data <- data.frame(group = d$state, tau = d$beta, se = d$se, no_diploma = d$no_diploma)
  args <- list(data, model = "rubin", pooling = "partial",
               prior_hypermean = normal(0, s), prior_hypersd = normal(0, 0.5 * s),
               iter = 40000, chains = 4, control = list(adapt_delta = 0.99),
               refresh = 0, seed = 20261113)
  if (covariate) args <- c(args, list(covariates = "no_diploma", prior_beta = normal(0, 0.5 * s)))
  suppressMessages(do.call(baggr, args))
}

baggr_draws <- function(fit, covariate) {
  # Draws of the parameters reported in pooling_hyper.csv.
  te <- treatment_effect(fit, message = FALSE)
  hold <- policy_covariate()
  hold <- hold[hold$state %in% HOLDOUT, ]
  new <- data.frame(no_diploma = c(0, hold$no_diploma))   # new diploma-withheld state, then CT, PA
  # Predictive draws, one column per row of `new`. With newdata, effect_draw returns
  # [1 x rows x draws]; without covariates, every new state has the same predictive distribution.
  pred <- if (covariate) t(effect_draw(fit, newdata = new, message = FALSE)[1, , ])
          else replicate(nrow(new), effect_draw(fit, message = FALSE))
  out <- list(mu = as.vector(te$tau), sigma_beta = as.vector(te$sigma_tau), new_state = pred[, 1])
  for (k in seq_len(nrow(hold))) out[[paste0("predict_", hold$state[k])]] <- pred[, k + 1]
  if (covariate) out$delta <- as.vector(fixed_effects(fit))
  out
}

# ---- Main ----------------------------------------------------------------------------------
est   <- read_estimates()
exact <- read.csv(file.path(TABLES, "pooling_hyper.csv"))
exact <- exact[exact$input_spec == INPUT & exact$prior == "main", ]
rows  <- list()
for (o in unique(exact$outcome)) for (m in unique(exact$model[exact$outcome == o])) {
  cov <- m == "covariate"
  fit <- fit_baggr(est[est$outcome == o, ], cov, OUTCOME_SCALE[[o]])
  rhat <- max(rstan::summary(fit$fit)$summary[, "Rhat"], na.rm = TRUE)
  draws <- baggr_draws(fit, cov)
  for (p in names(draws)) {
    e <- exact[exact$outcome == o & exact$model == m & exact$parameter == p, ]
    b <- summarise(draws[[p]])
    rows[[length(rows) + 1]] <- data.frame(
      outcome = o, model = m, parameter = p,
      exact_mean = e$mean, exact_q025 = e$q025, exact_q975 = e$q975,
      baggr_mean = b[["mean"]], baggr_q025 = b[["q025"]], baggr_q975 = b[["q975"]],
      max_rhat = rhat,
      match = abs(b[["mean"]] - e$mean) < 0.1 * e$sd &&
              abs(b[["q025"]] - e$q025) < 0.2 * e$sd && abs(b[["q975"]] - e$q975) < 0.2 * e$sd)
  }
}
check <- do.call(rbind, rows)
write.csv(check, file.path(TABLES, "pooling_baggr_check.csv"), row.names = FALSE)
print(check[, c("outcome", "model", "parameter", "exact_mean", "baggr_mean", "max_rhat", "match")],
      row.names = FALSE, digits = 3)
message(sprintf("%d of %d parameters match", sum(check$match), nrow(check)))
