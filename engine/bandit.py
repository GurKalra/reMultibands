"""
bandit.py

Segmented Thompson Sampling bandit for reMultiBands -- with an ADDITIVE
LOG-ODDS DECOMPOSITION of bank effects and network effects.

Why additive, not nested pooling:
    An earlier version tried nesting network INSIDE the bank/error_code
    segmentation (80 fine segments, falling back to a single global pool
    when thin). That failed: the fallback pool averaged across ALL
    banks, which washed out the strong bank-specific signal that used to
    converge quickly in the simpler 20-segment version, while the actual
    benefit (network awareness) was subtle by design. More data didn't
    fix it, because the problem was structural, not a data-volume problem.

    The fix: learn bank effects and network effects as two SEPARATE,
    independently-pooled beliefs, and combine them at decision time
    instead of nesting one inside the other:

        1. BASE belief: Beta posterior per (bank, error_code) -- exactly
           like the original, well-converging 20-segment design. Full
           statistical power, never diluted by network.
        2. NETWORK belief: Beta posterior per payment_network, pooled
           across ALL banks and error codes. With only 4 networks, this
           pool is large and converges fast, independent of any single
           bank+error combo.

    At decision time, a network's effect is measured against the
    UNWEIGHTED AVERAGE (in log-odds space) of ALL networks' current
    posteriors for that arm -- NOT a separately-tracked "global" pool fed
    raw observations. An earlier version of this file tried a real global
    pool and had a real bug: whichever network happened to have the most
    transaction volume silently dominated what "global" meant, making
    every OTHER (lower-volume) network look artificially worse just for
    being under-observed relative to that one network -- not because it
    actually performed worse. Deriving the reference as an unweighted
    average across networks' own posteriors fixes this: every network
    counts equally toward defining "normal," regardless of how much
    traffic it gets. This is the standard, textbook-correct way to do
    "effect coding" / deviation contrasts in an additive model (a
    category's effect = its own mean minus the unweighted grand mean of
    all category means).

        network_effect  = logit(this_network_belief) - grand_mean_logit(all networks)
        combined_belief = sigmoid( logit(base_belief) + network_effect )

    This assumes bank effects and network effects are roughly INDEPENDENT
    (additive) -- a real simplification of production reality, but one
    that happens to exactly match how this project's own synthetic
    ground truth was constructed (data/generate_data.py builds
    probabilities as base_probability + network_modifier, with no
    bank-network interaction term). In a real production system, this
    assumption should be actively monitored: once a specific fine segment
    accumulates enough of its OWN real observations to show a persistent,
    statistically real gap between what the additive model predicts and
    what actually happens, that segment can "graduate" to tracking its
    own independent posterior instead of relying on the additive
    approximation -- the same self-correcting philosophy already used
    throughout this project (informed priors get corrected by real data),
    just applied one level up, to model structure instead of just
    parameters.

This file is intentionally "dumb" about WHY a segment behaves a certain
way -- it only tracks alpha/beta counts across the two pools. All the
informed starting beliefs live in priors.py; all the compliance/stopping
logic lives in rule_engine.py.

Risk-adjusted reward & revenue weighting (unchanged from before): update()
still accepts risk_penalty and revenue_weight, applied identically to
BOTH tracked pools (base, network) since every real observation is
evidence for both margins at once.
"""

import math
import random

from engine.priors import build_base_prior_table, build_network_prior_table, build_global_prior_table, ARMS

_EPS = 1e-4  # clip probabilities away from 0/1 before taking logit, to avoid +/- infinity


def _clip(p):
    return min(1 - _EPS, max(_EPS, p))


def _logit(p):
    p = _clip(p)
    return math.log(p / (1 - p))


def _sigmoid(x):
    return 1 / (1 + math.exp(-x))


class SegmentedThompsonBandit:
    def __init__(self, base_prior_table=None, network_prior_table=None, global_prior_table=None):
        """
        base_prior_table: dict of "Bank|error_code" -> {arm: (alpha, beta)}.
            Defaults to the informed BASE priors from priors.py.
        network_prior_table: dict of network -> {arm: (alpha, beta)}.
            Defaults to the neutral NETWORK priors from priors.py.
        global_prior_table: dict of arm -> (alpha, beta).
            Defaults to the neutral GLOBAL prior from priors.py.
        """
        self.base_priors = base_prior_table if base_prior_table is not None else build_base_prior_table()
        self.network_priors = network_prior_table if network_prior_table is not None else build_network_prior_table()
        # NOTE: global_prior_table param kept for interface compatibility
        # but no longer used to seed a tracked pool -- see module
        # docstring's bugfix note. The "global reference" is now DERIVED
        # on the fly as an unweighted average across network posteriors,
        # not fed raw pooled observations (which let high-volume networks
        # silently bias what "normal" looks like for low-volume ones).

        # live posterior state for two tracked pools (base + network).
        self.base_posteriors = {
            seg: {arm: list(ab) for arm, ab in arms.items()} for seg, arms in self.base_priors.items()
        }
        self.network_posteriors = {
            net: {arm: list(ab) for arm, ab in arms.items()} for net, arms in self.network_priors.items()
        }
        self._networks = list(self.network_priors.keys())

        # decision counters (arm PULLS, i.e. times chosen), keyed by the
        # full fine segment for audit/debugging purposes
        self.pull_counts = {}
        # real-observation counts, for dashboard transparency
        self.base_observation_counts = {
            seg: {arm: 0 for arm in arms} for seg, arms in self.base_priors.items()
        }
        self.network_observation_counts = {
            net: {arm: 0 for arm in arms} for net, arms in self.network_priors.items()
        }

    def _base_key(self, bank, error_code):
        return f"{bank}|{error_code}"

    def _fine_key(self, bank, error_code, network):
        return f"{bank}|{error_code}|{network}"

    def _combined_probability(self, base_alpha, base_beta, network, arm, sample=True):
        """
        Combines base + network beliefs into one probability via additive
        log-odds. The reference point a network's effect is measured
        against is the UNWEIGHTED AVERAGE (in log-odds space) across ALL
        networks' current posterior MEANS for this arm.

        IMPORTANT: only the BASE posterior and THIS transaction's own
        NETWORK posterior are stochastically sampled (genuine Thompson
        Sampling exploration on the two things actually being learned for
        this decision). The other networks contributing to the grand-mean
        reference use their stable posterior MEANS, not fresh random
        draws. An earlier version sampled all 4 networks fresh on every
        single decision, which injected unnecessary noise into decisions
        that had nothing to do with those other networks -- even a
        highly-confident base posterior could get its choice flipped by
        random jitter in networks irrelevant to that specific
        transaction. Keeping the reference stable (means) while still
        exploring stochastically on what's actually relevant (base + this
        network) removes that noise without giving up real exploration.

        If sample=True: base_p and this-network's p are random Beta draws
        (Thompson Sampling); the grand-mean reference uses all networks'
        current means (stable). If sample=False: everything uses means
        (deterministic point estimate, for snapshot()/dashboard display).
        """
        network_means = {
            net: (self.network_posteriors[net][arm][0] / sum(self.network_posteriors[net][arm]))
            for net in self._networks
        }
        grand_mean_logit = sum(_logit(p) for p in network_means.values()) / len(network_means)

        if sample:
            base_p = random.betavariate(base_alpha, base_beta)
            net_alpha, net_beta = self.network_posteriors[network][arm]
            this_network_p = random.betavariate(net_alpha, net_beta)
        else:
            base_p = base_alpha / (base_alpha + base_beta)
            this_network_p = network_means[network]

        network_effect = _logit(this_network_p) - grand_mean_logit
        combined_logit = _logit(base_p) + network_effect
        return _sigmoid(combined_logit), network_effect

    def select_arm(self, bank, error_code, network, excluded_arms=None):
        """
        For each available arm, samples base/network beliefs and combines
        them via additive log-odds into one probability, then picks the
        arm with the highest combined sample (Thompson Sampling on top of
        the additive decomposition).

        excluded_arms: optional set/list of arms to exclude (used by
        rule_engine.py's "soft zone" near the network cap).

        Returns: (chosen_arm, sampled_values_dict) -- sampled_values are
        the combined probabilities used for the decision (for audit logging).
        """
        base_key = self._base_key(bank, error_code)
        if base_key not in self.base_posteriors:
            raise KeyError(f"Unknown (bank, error_code): {base_key}")
        if network not in self.network_posteriors:
            raise KeyError(f"Unknown network: {network}")

        excluded_arms = set(excluded_arms or [])
        available_arms = [a for a in ARMS if a not in excluded_arms]
        if not available_arms:
            raise ValueError("No arms available to select from (all excluded).")

        sampled_values = {}
        for arm in available_arms:
            base_alpha, base_beta = self.base_posteriors[base_key][arm]
            combined_p, _ = self._combined_probability(base_alpha, base_beta, network, arm, sample=True)
            sampled_values[arm] = combined_p

        chosen_arm = max(sampled_values, key=sampled_values.get)

        fine_key = self._fine_key(bank, error_code, network)
        self.pull_counts.setdefault(fine_key, {a: 0 for a in ARMS})
        self.pull_counts[fine_key][chosen_arm] += 1

        return chosen_arm, sampled_values

    def update(self, bank, error_code, network, arm, success: bool, risk_penalty: float = 0.0,
               revenue_weight: float = 1.0):
        """
        Feeds back an observed outcome into BOTH tracked pools (base,
        network) -- every real observation is evidence for both margins
        simultaneously.

        success=True  -> alpha += revenue_weight on both pools
        success=False -> beta  += revenue_weight + risk_penalty on both
                          pools (risk_penalty is NOT scaled by revenue --
                          it's a compliance cost, not a money one)
        """
        base_key = self._base_key(bank, error_code)
        if base_key not in self.base_posteriors:
            raise KeyError(f"Unknown (bank, error_code): {base_key}")
        if network not in self.network_posteriors:
            raise KeyError(f"Unknown network: {network}")
        if arm not in self.base_posteriors[base_key]:
            raise KeyError(f"Unknown arm: {arm}")

        revenue_weight = max(0.01, revenue_weight)

        if success:
            self.base_posteriors[base_key][arm][0] += revenue_weight
            self.network_posteriors[network][arm][0] += revenue_weight
        else:
            fail_weight = revenue_weight + max(0.0, risk_penalty)
            self.base_posteriors[base_key][arm][1] += fail_weight
            self.network_posteriors[network][arm][1] += fail_weight

        self.base_observation_counts[base_key][arm] += 1
        self.network_observation_counts[network][arm] += 1

    def get_posterior_mean(self, bank, error_code, network, arm):
        """Returns the current COMBINED (base+network) point-estimate probability for one arm."""
        base_key = self._base_key(bank, error_code)
        base_alpha, base_beta = self.base_posteriors[base_key][arm]
        combined_p, _ = self._combined_probability(base_alpha, base_beta, network, arm, sample=False)
        return combined_p

    def snapshot(self, bank, error_code, network):
        """
        Returns per-arm base/network posterior means, the unweighted
        grand-mean reference across all networks, the network's measured
        effect (in probability-shift terms, for readability), the
        combined point-estimate probability, and observation counts --
        useful for the dashboard's "how is this network shifting outcomes
        for this bank+error type" visualization.
        """
        base_key = self._base_key(bank, error_code)
        fine_key = self._fine_key(bank, error_code, network)
        result = {}
        for arm in ARMS:
            base_alpha, base_beta = self.base_posteriors[base_key][arm]
            base_mean = base_alpha / (base_alpha + base_beta)

            net_alpha, net_beta = self.network_posteriors[network][arm]
            net_mean = net_alpha / (net_alpha + net_beta)

            grand_mean_logit = sum(
                _logit(self.network_posteriors[n][arm][0] / sum(self.network_posteriors[n][arm]))
                for n in self._networks
            ) / len(self._networks)

            combined_p, network_effect_logit = self._combined_probability(
                base_alpha, base_beta, network, arm, sample=False
            )
            # convert the network's logit effect into an intuitive
            # "probability points shifted" number for display: how much
            # higher/lower the combined estimate is vs. the base alone
            base_only_p = _sigmoid(_logit(base_mean))
            network_shift = combined_p - base_only_p

            result[arm] = {
                "base_mean": round(base_mean, 3),
                "network_mean": round(net_mean, 3),
                "grand_mean_across_networks": round(_sigmoid(grand_mean_logit), 3),
                "combined_probability": round(combined_p, 3),
                "network_effect_shift": round(network_shift, 3),  # +/- probability points contributed by this network
                "n_base_observations": self.base_observation_counts[base_key][arm],
                "n_network_observations": self.network_observation_counts[network][arm],
                "pulls": self.pull_counts.get(fine_key, {}).get(arm, 0),
            }
        return result


if __name__ == "__main__":
    # smoke test 1: confirm a network with no data yet has ~zero effect
    # (network_effect_shift should start near 0, since network and global
    # pools start from the same neutral prior).
    bandit = SegmentedThompsonBandit()
    bank, error_code, network = "HDFC", "timeout", "UPI_AUTOPAY"

    print(f"Segment: {bank}|{error_code}|{network}\n")
    print("Snapshot BEFORE any observations (network effect should be ~0):")
    for arm, stats in bandit.snapshot(bank, error_code, network).items():
        print(f"    {arm:20s} base={stats['base_mean']:.3f}  network={stats['network_mean']:.3f}  "
              f"combined={stats['combined_probability']:.3f}  network_shift={stats['network_effect_shift']:+.3f}")

    # smoke test 2: feed UPI_AUTOPAY strong evidence that whatsapp_escalate
    # converts well on that rail, ACROSS several different banks/error
    # codes (as real traffic would) -- confirm the NETWORK pool picks up
    # a positive effect that then shows up for OTHER banks on the same
    # network, without needing their own direct data.
    random.seed(0)
    for bank_i in ["HDFC", "SBI", "ICICI"]:
        for _ in range(20):
            bandit.update(bank_i, "timeout", "UPI_AUTOPAY", "whatsapp_escalate", success=True, revenue_weight=1.0)

    print("\nAfter 60 successful whatsapp_escalate observations on UPI_AUTOPAY, spread across 3 banks:")
    print(f"  HDFC|timeout|UPI_AUTOPAY (received direct data):")
    stats = bandit.snapshot("HDFC", "timeout", "UPI_AUTOPAY")["whatsapp_escalate"]
    print(f"    base={stats['base_mean']:.3f}  network={stats['network_mean']:.3f}  "
          f"combined={stats['combined_probability']:.3f}  network_shift={stats['network_effect_shift']:+.3f}  "
          f"n_network_obs={stats['n_network_observations']}")

    print(f"\n  Axis|timeout|UPI_AUTOPAY (received ZERO direct data, different bank):")
    stats2 = bandit.snapshot("Axis", "timeout", "UPI_AUTOPAY")["whatsapp_escalate"]
    print(f"    base={stats2['base_mean']:.3f}  network={stats2['network_mean']:.3f}  "
          f"combined={stats2['combined_probability']:.3f}  network_shift={stats2['network_effect_shift']:+.3f}  "
          f"n_network_obs={stats2['n_network_observations']}")

    print(f"\n  Axis|timeout|Visa (different bank AND different network -- should see NO shift):")
    stats3 = bandit.snapshot("Axis", "timeout", "Visa")["whatsapp_escalate"]
    print(f"    base={stats3['base_mean']:.3f}  network={stats3['network_mean']:.3f}  "
          f"combined={stats3['combined_probability']:.3f}  network_shift={stats3['network_effect_shift']:+.3f}  "
          f"n_network_obs={stats3['n_network_observations']}")