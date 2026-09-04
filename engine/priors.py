"""
priors.py

Seeds informed Beta(alpha, beta) priors for THREE independent pools, used
by the additive log-odds decomposition in bandit.py:

    1. BASE priors: one per (bank, error_code) -- 20 combinations. This
       is where bank-specific behavior is learned, using the SAME
       informed, error_code-driven heuristic as before (bank-agnostic
       starting belief; the bandit discovers bank-specific differences
       from real data).
    2. NETWORK priors: one per payment_network -- 4 combinations, pooled
       across ALL banks and error codes. Deliberately NEUTRAL (no
       assumed direction) -- we don't want to bake in a guess about
       whether UPI or Visa is "better," we want the bandit to discover
       that from real data.
    3. GLOBAL prior: one single arm-level reference, pooled across
       EVERYTHING. Also neutral. Kept here for interface compatibility;
       bandit.py no longer tracks a live global pool from this (see
       bandit.py's module docstring for why) -- the reference is now
       derived on the fly from the network posteriors instead.

Why additive, not nested: see engine/bandit.py's module docstring for
the full reasoning. Short version -- our own synthetic ground truth was
built as base_probability + network_modifier (additive, no bank-network
interaction term), so an additive learning model is the structurally
correct match for this data, not just a convenient simplification.
"""

ARMS = ["retry_2h", "retry_24h", "retry_72h", "whatsapp_escalate"]

BANKS = ["HDFC", "SBI", "ICICI", "Axis", "Kotak"]
ERROR_CODES = ["timeout", "insufficient_funds", "hard_decline", "issuer_unavailable"]
PAYMENT_NETWORKS = ["UPI_AUTOPAY", "RuPay", "Visa", "Mastercard"]

# Prior "shape" per error_code: relative belief weight per arm (not
# probabilities -- just relative strength, normalized into alpha/beta below).
ERROR_CODE_HEURISTICS = {
    "timeout": {
        "retry_2h": 0.20,
        "retry_24h": 0.65,
        "retry_72h": 0.35,
        "whatsapp_escalate": 0.45,
    },
    "insufficient_funds": {
        "retry_2h": 0.10,
        "retry_24h": 0.25,
        "retry_72h": 0.60,
        "whatsapp_escalate": 0.45,
    },
    "hard_decline": {
        "retry_2h": 0.05,
        "retry_24h": 0.05,
        "retry_72h": 0.05,
        "whatsapp_escalate": 0.55,
    },
    "issuer_unavailable": {
        "retry_2h": 0.55,
        "retry_24h": 0.30,
        "retry_72h": 0.20,
        "whatsapp_escalate": 0.45,
    },
}

# BASE prior confidence weight (alpha + beta). A meaningful starting
# belief, meant to be overridden by real data after ~5-10 observations.
BASE_PRIOR_WEIGHT = 8.0

# NETWORK / GLOBAL prior confidence weight -- deliberately weak/neutral
# (mean 0.5, low total weight) so real data dominates quickly. These
# pools see MUCH more data per update than any single base segment (every
# transaction contributes to exactly one network pool), so they converge
# fast even starting from "no assumed effect."
NEUTRAL_PRIOR_WEIGHT = 4.0
NEUTRAL_SUCCESS_WEIGHT = 0.5


def _alpha_beta(success_weight, weight):
    alpha = weight * success_weight
    beta = weight * (1 - success_weight)
    return max(alpha, 0.5), max(beta, 0.5)


def build_base_prior_table():
    """
    BASE priors: one entry per (bank, error_code). Returns a dict keyed
    "Bank|error_code" -> {arm: (alpha, beta)}. Bank-agnostic on purpose
    -- every bank starts from the same error_code-driven heuristic;
    bank-specific behavior is learned from data.
    """
    prior_table = {}
    for bank in BANKS:
        for error_code in ERROR_CODES:
            key = f"{bank}|{error_code}"
            heuristics = ERROR_CODE_HEURISTICS[error_code]
            prior_table[key] = {
                arm: _alpha_beta(heuristics[arm], BASE_PRIOR_WEIGHT)
                for arm in ARMS
            }
    return prior_table


def build_network_prior_table():
    """
    NETWORK priors: one entry per payment_network, pooled across all
    banks/error codes. Returns a dict keyed network -> {arm: (alpha, beta)}.
    Neutral (mean 0.5) -- no assumed direction for any network.
    """
    return {
        network: {arm: _alpha_beta(NEUTRAL_SUCCESS_WEIGHT, NEUTRAL_PRIOR_WEIGHT) for arm in ARMS}
        for network in PAYMENT_NETWORKS
    }


def build_global_prior_table():
    """
    GLOBAL prior: a single arm-level reference (kept for interface
    compatibility -- see module docstring). Returns {arm: (alpha, beta)}.
    Neutral (mean 0.5).
    """
    return {arm: _alpha_beta(NEUTRAL_SUCCESS_WEIGHT, NEUTRAL_PRIOR_WEIGHT) for arm in ARMS}


if __name__ == "__main__":
    base_table = build_base_prior_table()
    network_table = build_network_prior_table()
    global_table = build_global_prior_table()

    print(f"Built BASE priors for {len(base_table)} (bank, error_code) segments")
    print(f"Built NETWORK priors for {len(network_table)} networks (neutral, mean 0.5)")
    print(f"Built GLOBAL prior for {len(global_table)} arms (neutral, mean 0.5, fully pooled)\n")

    sample_key = "HDFC|timeout"
    print(f"Sample base segment ({sample_key}):")
    for arm, (a, b) in base_table[sample_key].items():
        print(f"    {arm:20s} alpha={a:.2f}  beta={b:.2f}  implied_prior_success_rate={a/(a+b):.2f}")

    print(f"\nNetwork prior for UPI_AUTOPAY (should be neutral, ~0.5 for all arms):")
    for arm, (a, b) in network_table["UPI_AUTOPAY"].items():
        print(f"    {arm:20s} alpha={a:.2f}  beta={b:.2f}  implied_prior_success_rate={a/(a+b):.2f}")