# Pool the state estimates with a Bayesian hierarchical model (Meager 2019, AEJ: Applied).
#
# Inputs (written by 06_first_stage.py and 08_reduced_form.py):
#   output/tables/first_stage_by_state.csv    beta, se per state and spec (FAFSA completion)
#   output/tables/reduced_form_by_state.csv   beta, se per state and spec (college enrollment)
# Input spec (DECISIONS 2026-11-15): common_window (e = -3 ... 0 in every state, so every state's
# estimate has the same pre-period baseline and post class); sensitivity: main (Deneault's window,
# e = -4 ... +1 where available, so windows differ across states), main prior only.
#   data/policy/state_mandates.csv            graduation_consequence -> state-level covariate
#
# Model, for each outcome, states k = 1..K:
#   beta_hat_k ~ N(beta_k, se_k^2)       (state estimate, SE treated as known)
#   beta_k ~ N(mu + delta * x_k, sigma_beta^2)  (true state effects, x_k = 1 if no diploma consequence)
# mu = hypermean (average effect), sigma_beta = hyper-SD, delta = covariate coefficient.
# Main priors (weakly informative, on the 0-1 dose scale; all scales halved for enrollment):
#   mu ~ N(0, 1), delta ~ N(0, 0.5^2), sigma_beta ~ Half-Normal(0, 0.5).
# Sensitivity: flat mu, delta with uniform(0, 1) sigma_beta (BDA3 default); half-Cauchy(0, 0.05) sigma_beta.
# The posterior is exact: sigma_beta is drawn from its marginal on a fine grid, then (mu, delta) and
# beta_k from their normal conditionals (Gelman et al., BDA3 ch. 5). Base R only.
# Pooling metrics: omega_k = se_k^2 / (sigma_beta^2 + se_k^2) (Meager eq. 6) at the posterior mean of
# sigma_beta^2, its average omega_bar, and Gelman & Pardoe's (2006) lambda (Meager eq. 8).
#
# Outputs (output/tables/, output/figures/):
#   pooling_hyper.csv       mu, delta, sigma_beta, and predicted effects for CT, PA and a new state (both inputs)
#   pooling_states.csv      each state's estimate, its posterior (shrunk) effect, and pooling metrics (both models)
#   pooling_loo.csv         leave-one-state-out: predicted effect of the dropped state vs. its estimate
#   pooling_forest.png      covariate model: state estimates, shrunk effects, and each diploma group's center
#
# Run from the repository root:  Rscript code/12_aggregation.R

set.seed(20261113)

# ---- Paths (mirror code/config.py) ---------------------------------------------------------
script_dir <- function() {
  # Folder of this script when run with Rscript; fall back to code/ under the working directory.
  arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(arg)) dirname(normalizePath(sub("^--file=", "", arg))) else file.path(getwd(), "code")
}
ROOT   <- dirname(script_dir())
OUTPUT <- file.path(ROOT, "output")
POLICY <- file.path(ROOT, "data", "policy", "state_mandates.csv")

N_DRAWS  <- 20000                               # posterior draws per model
SIGMA_GRID <- seq(0, 1, length.out = 5001)[-1]  # effects are on a 0-1 rate scale, so sigma_beta < 1
HOLDOUT  <- c("CT", "PA")                       # no post-mandate data yet: out-of-sample predictions
MAIN_INPUT <- "common_window"                   # step 6/8 spec pooled in the main analysis
SENSITIVITY_INPUT <- "main"                     # Deneault's window, differs across states

# Prior scale by outcome: the enrollment effects are smaller, so all prior scales are halved.
OUTCOME_SCALE <- c(fafsa_completion = 1, college_enrollment = 0.5)

prior_sets <- function(s) {
  # Prior sets for an outcome with scale s. b_sd: prior SDs of (mu, delta), Inf = flat.
  # log_sigma: log prior density of sigma_beta, up to a constant.
  list(
    main           = list(b_sd = c(1, 0.5) * s, log_sigma = function(t) dnorm(t, 0, 0.5 * s, log = TRUE)),
    flat_uniform   = list(b_sd = c(Inf, Inf),    log_sigma = function(t) 0 * t),
    half_cauchy_05 = list(b_sd = c(1, 0.5) * s, log_sigma = function(t) dcauchy(t, 0, 0.05, log = TRUE))
  )
}
MAIN_PRIOR <- "main"

# ---- Inputs --------------------------------------------------------------------------------
read_estimates <- function(spec = MAIN_INPUT) {
  # One row per state x outcome from one step-6/8 specification, with the policy covariate.
  fs <- read.csv(file.path(OUTPUT, "tables", "first_stage_by_state.csv"))
  rf <- read.csv(file.path(OUTPUT, "tables", "reduced_form_by_state.csv"))
  fs <- transform(fs[fs$spec == spec, c("state", "beta", "se")], outcome = "fafsa_completion")
  rf <- transform(rf[rf$spec == spec, c("state", "beta", "se")], outcome = "college_enrollment")
  est <- rbind(fs, rf)
  est <- merge(est, policy_covariate(), by = "state", all.x = TRUE)
  stopifnot(!anyNA(est$no_diploma), !anyDuplicated(est[c("state", "outcome")]))
  for (o in unique(est$outcome))
    message(sprintf("%s, %s: %d states (%s)", spec, o, sum(est$outcome == o),
                    paste(sort(est$state[est$outcome == o]), collapse = " ")))
  attr(est, "spec") <- spec
  est
}

policy_covariate <- function() {
  # x_k = 1 when the mandate does not withhold the diploma (CA, NY: LEA requirement; PA).
  m <- read.csv(POLICY)
  data.frame(state = m$state, no_diploma = as.integer(m$graduation_consequence == "none"))
}

# ---- Model ---------------------------------------------------------------------------------
fit_pool <- function(y, se, X, prior) {
  # Exact posterior draws of the normal hierarchical model with known SEs.
  # y, se: state estimates and SEs; X: K x p design (intercept, covariate);
  # prior: one element of prior_sets() (normal or flat prior on b, log prior on sigma_beta).
  # Returns draws of b (mu, delta), sigma_beta, and beta_k (K columns).
  X <- as.matrix(X)
  P0 <- diag(1 / prior$b_sd[seq_len(ncol(X))]^2, ncol(X))   # prior precision of b (0 = flat)
  cond_b <- function(t) {
    # Normal conditional of b given sigma_beta = t: precision A, mean m.
    w <- 1 / (se^2 + t^2)
    A <- crossprod(X, w * X) + P0
    list(w = w, A = A, m = solve(A, crossprod(X, w * y)))
  }
  log_post <- sapply(SIGMA_GRID, function(t) {
    # log p(sigma_beta | y) with b integrated out under its normal (or flat) prior
    cb <- cond_b(t)
    -0.5 * determinant(cb$A)$modulus + 0.5 * sum(log(cb$w)) -
      0.5 * (sum(cb$w * y^2) - drop(crossprod(cb$m, cb$A %*% cb$m)))
  }) + prior$log_sigma(SIGMA_GRID)
  p <- exp(log_post - max(log_post))
  sigma <- sample(SIGMA_GRID, N_DRAWS, replace = TRUE, prob = p)

  b <- t(sapply(sigma, function(t) {
    cb <- cond_b(t)
    drop(cb$m + backsolve(chol(cb$A), rnorm(ncol(X))))   # draw from N(m, A^-1)
  }))
  if (ncol(X) == 1) b <- t(b)
  prior_mean <- b %*% t(X)                                # N_DRAWS x K: mu + delta * x_k
  # beta_k | b, sigma_beta, y is normal with precision 1/sigma^2 + 1/se_k^2 and mean
  # omega_k * (mu + delta * x_k) + (1 - omega_k) * beta_hat_k, omega_k = se_k^2 / (sigma^2 + se_k^2) (eq. 6).
  prec <- outer(1 / sigma^2, rep(1, length(y))) + outer(rep(1, N_DRAWS), 1 / se^2)
  m <- (prior_mean / sigma^2 + outer(rep(1, N_DRAWS), y / se^2)) / prec
  beta_k <- m + matrix(rnorm(length(m)), N_DRAWS) / sqrt(prec)
  list(b = b, sigma_beta = sigma, beta_k = beta_k)
}

predict_new <- function(fit, x) {
  # Posterior predictive effect for a new state with covariate row x (e.g. c(1, 0)).
  drop(fit$b %*% x) + rnorm(N_DRAWS) * fit$sigma_beta
}

summarise <- function(draws) {
  # Posterior mean, SD, 95% interval, and share of draws above zero.
  c(mean = mean(draws), sd = sd(draws), q025 = unname(quantile(draws, 0.025)),
    q975 = unname(quantile(draws, 0.975)), p_gt0 = mean(draws > 0))
}

design <- function(d, covariate) {
  # Intercept only, or intercept + no-diploma indicator (only if both groups are present).
  if (covariate && length(unique(d$no_diploma)) == 2) cbind(1, d$no_diploma) else matrix(1, nrow(d))
}

# ---- Runs ----------------------------------------------------------------------------------
hyper_rows <- function(est, priors = names(prior_sets(1))) {
  # mu, delta, sigma_beta, and predictive effects for each outcome x model x prior.
  out <- list()
  holdout <- policy_covariate()
  holdout <- holdout[holdout$state %in% HOLDOUT, ]
  for (o in unique(est$outcome)) for (cov in c(FALSE, TRUE)) for (pr in priors) {
    d <- est[est$outcome == o, ]
    X <- design(d, cov)
    if (cov && ncol(X) == 1) next
    fit <- fit_pool(d$beta, d$se, X, prior_sets(OUTCOME_SCALE[[o]])[[pr]])
    par <- list(mu = fit$b[, 1], sigma_beta = fit$sigma_beta, new_state = predict_new(fit, c(1, 0)[seq_len(ncol(X))]))
    if (cov) par$delta <- fit$b[, 2]
    for (s in seq_len(nrow(holdout)))
      par[[paste0("predict_", holdout$state[s])]] <-
        predict_new(fit, c(1, holdout$no_diploma[s])[seq_len(ncol(X))])
    for (nm in names(par))
      out[[length(out) + 1]] <- data.frame(input_spec = attr(est, "spec"), outcome = o,
                                           model = if (cov) "covariate" else "no_covariate",
                                           prior = pr, n_states = nrow(d), parameter = nm,
                                           t(summarise(par[[nm]])))
  }
  do.call(rbind, out)
}

state_rows <- function(est) {
  # Each state's estimate, its shrunk posterior effect, and pooling metrics (main prior), for both models.
  # In the covariate model, states are pulled toward their own center mu + delta * x_k (spec eq. 6).
  out <- list()
  for (o in unique(est$outcome)) for (cov in c(FALSE, TRUE)) {
    d <- est[est$outcome == o, ]
    X <- design(d, cov)
    if (cov && ncol(X) == 1) next
    fit <- fit_pool(d$beta, d$se, X, prior_sets(OUTCOME_SCALE[[o]])[[MAIN_PRIOR]])
    s <- t(apply(fit$beta_k, 2, summarise))
    omega <- d$se^2 / (mean(fit$sigma_beta^2) + d$se^2)   # weight on the cross-state center
    center <- fit$b %*% t(X)                               # draws of each state's center mu + delta * x_k
    out[[length(out) + 1]] <- data.frame(
      input_spec = attr(est, "spec"), outcome = o, model = if (cov) "covariate" else "no_covariate", state = d$state,
      no_diploma = d$no_diploma, beta = d$beta, se = d$se, center_mean = colMeans(center),
      center_q025 = apply(center, 2, quantile, 0.025), center_q975 = apply(center, 2, quantile, 0.975),
      beta_k_mean = s[, "mean"], beta_k_q025 = s[, "q025"], beta_k_q975 = s[, "q975"],
      omega_k = omega, omega_bar = mean(omega), lambda_gp = gelman_pardoe(fit, X))
  }
  do.call(rbind, out)
}

gelman_pardoe <- function(fit, X) {
  # Gelman & Pardoe (2006) pooling factor: 1 - var_k(E[eps_k]) / E[var_k(eps_k)],
  # eps_k = beta_k - (mu + delta * x_k) from posterior draws (= beta_k - mu without the covariate).
  eps <- fit$beta_k - fit$b %*% t(X)
  1 - var(colMeans(eps)) / mean(apply(eps, 1, var))
}

loo_rows <- function(est) {
  # Drop each state, refit, and predict the dropped state's effect (main prior, no covariate).
  out <- list()
  for (o in unique(est$outcome)) {
    d <- est[est$outcome == o, ]
    for (k in seq_len(nrow(d))) {
      fit <- fit_pool(d$beta[-k], d$se[-k], design(d[-k, ], FALSE), prior_sets(OUTCOME_SCALE[[o]])[[MAIN_PRIOR]])
      pred <- summarise(predict_new(fit, 1))
      out[[length(out) + 1]] <- data.frame(
        input_spec = attr(est, "spec"), outcome = o, dropped = d$state[k], beta = d$beta[k], se = d$se[k],
        mu_mean = mean(fit$b[, 1]), sigma_beta_mean = mean(fit$sigma_beta),
        pred_mean = pred[["mean"]], pred_q025 = pred[["q025"]], pred_q975 = pred[["q975"]],
        inside_95 = d$beta[k] >= pred[["q025"]] && d$beta[k] <= pred[["q975"]])
    }
  }
  do.call(rbind, out)
}

GROUP_COL   <- c("#2a78d6", "#eb6834")   # diploma withheld (x = 0), no diploma (x = 1); categorical slots 1-2
GROUP_LABEL <- c("Diploma withheld", "No diploma")
OUTCOME_LABEL <- c(fafsa_completion = "FAFSA completion", college_enrollment = "College enrollment")

forest_plot <- function(states, path) {
  # Covariate model (main prior): each state's estimate (open) with 95% CI and its shrunk effect
  # (filled), colored by diploma group; below, each group's center (mu, mu + delta) with 95% interval.
  png(path, width = 1800, height = 1050, res = 150)
  op <- par(mfrow = c(1, 2), mar = c(4, 9, 3, 1), oma = c(2.5, 0, 0, 0))
  for (o in unique(states$outcome)) {
    d <- states[states$outcome == o & states$model == "covariate", ]
    d <- d[order(d$beta), ]
    g <- d[!duplicated(d$no_diploma), ]; g <- g[order(-g$no_diploma), ]   # one center per group
    yc <- seq_len(nrow(g)) - 1; y <- seq_len(nrow(d)) + nrow(g)          # centers at the bottom
    col <- GROUP_COL[d$no_diploma + 1]
    lo <- d$beta - 1.96 * d$se; hi <- d$beta + 1.96 * d$se
    plot(NA, xlim = range(lo, hi, 0), ylim = c(-0.6, max(y) + 0.5), yaxt = "n",
         xlab = "Effect of dose x post", ylab = "", main = OUTCOME_LABEL[[o]])
    abline(v = 0, lty = 3, col = "grey50"); abline(h = nrow(g) - 0.5, col = "grey80")
    axis(2, at = y, labels = d$state, las = 1)
    axis(2, at = yc, labels = paste("Center:", tolower(GROUP_LABEL[g$no_diploma + 1])), las = 1, cex.axis = 0.8)
    segments(lo, y + 0.15, hi, y + 0.15, col = col); points(d$beta, y + 0.15, col = col)
    segments(d$beta_k_q025, y - 0.15, d$beta_k_q975, y - 0.15, col = col, lwd = 2)
    points(d$beta_k_mean, y - 0.15, pch = 19, col = col)
    gc <- GROUP_COL[g$no_diploma + 1]
    segments(g$center_q025, yc, g$center_q975, yc, col = gc, lwd = 6)
    points(g$center_mean, yc, pch = 23, bg = "white", col = gc, cex = 1.6, lwd = 2)
  }
  par(fig = c(0, 1, 0, 1), oma = c(0, 0, 0, 0), mar = c(0, 0, 0, 0), new = TRUE)   # legend below both panels
  plot.new()
  legend("bottom", c("State estimate (95% CI)", "Pooled state effect", "Group center", GROUP_LABEL),
         pch = c(1, 19, 23, 15, 15), col = c("grey30", "grey30", "grey30", GROUP_COL), bty = "n", cex = 0.85,
         horiz = TRUE)
  par(op); invisible(dev.off())
}

# ---- Main ----------------------------------------------------------------------------------
est    <- read_estimates()
hyper  <- rbind(hyper_rows(est), hyper_rows(read_estimates(SENSITIVITY_INPUT), priors = MAIN_PRIOR))
states <- state_rows(est)
loo    <- loo_rows(est)

dir.create(file.path(OUTPUT, "figures"), showWarnings = FALSE)
write.csv(hyper,  file.path(OUTPUT, "tables", "pooling_hyper.csv"),  row.names = FALSE)
write.csv(states, file.path(OUTPUT, "tables", "pooling_states.csv"), row.names = FALSE)
write.csv(loo,    file.path(OUTPUT, "tables", "pooling_loo.csv"),    row.names = FALSE)
forest_plot(states, file.path(OUTPUT, "figures", "pooling_forest.png"))

main <- hyper[hyper$model == "no_covariate" & hyper$prior == MAIN_PRIOR & hyper$parameter %in% c("mu", "sigma_beta"), ]
print(main[, c("input_spec", "outcome", "n_states", "parameter", "mean", "q025", "q975")], row.names = FALSE, digits = 3)
print(unique(states[, c("outcome", "model", "omega_bar", "lambda_gp")]), row.names = FALSE, digits = 3)
