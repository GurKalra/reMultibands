"""
reversal_model.py

Models "deemed approved" transactions -- a real, regulated phenomenon in
UPI: a transaction can appear successful (money debited) while its final
status is still unconfirmed, and only resolves (either truly succeeding
or reversing back to the customer) within a Turn Around Time window.

SOURCED: RBI's Turn Around Time (TAT) framework for UPI requires a
"deemed approved" transaction to auto-resolve within T+1 calendar day
for peer-to-peer transfers, or T+5 calendar days for MERCHANT payments.
Since this project models merchant/subscription mandate payments, T+5
is the applicable window (see REVERSAL_WINDOW_DAYS below).

NOT SOURCED (illustrative assumptions, disclosed as such): the RATE at
which a nominal "success" is actually provisional (PROVISIONAL_RATE),
and the rate at which a provisional transaction ultimately reverses
(REVERSAL_RATE_GIVEN_PROVISIONAL). RBI's framework defines the maximum
TIME WINDOW a rail must resolve within -- it does not publish how often
transactions actually land in this state or how often they end up
reversing. These two rates are reasonable, small, illustrative
assumptions chosen to make the phenomenon demonstrable without
overstating it.

Scope: this is currently modeled for UPI_AUTOPAY only, since that's the
network the T+5 TAT rule is sourced for. Card networks have an analogous
but functionally different phenomenon (chargebacks/disputes, with much
longer windows and different mechanics, driven by customer action rather
than rail-level "deemed approved" states) -- not modeled here; flagged as
a natural next extension, not built tonight.

Simplification, disclosed: this simulator resolves each transaction to
completion before moving to the next, rather than running a full
day-by-day event timeline. So instead of resolving each reversal exactly
T+5 days after its own transaction, this module resolves ALL pending
reversals in a single END-OF-RUN correction pass. The substance that
actually matters -- a delayed reward correction that claws back both
revenue and the bandit's learned belief -- is fully real; only the exact
scheduling mechanics are simplified.
"""

import random

REVERSAL_WINDOW_DAYS = 5  # SOURCED: RBI TAT, T+5 for merchant UPI payments

# Illustrative, NOT sourced -- see module docstring.
PROVISIONAL_RATE = 0.05                 # fraction of nominal "successes" that are actually provisional
REVERSAL_RATE_GIVEN_PROVISIONAL = 0.30  # fraction of provisional transactions that ultimately reverse

# Only UPI_AUTOPAY is modeled -- see module docstring's "Scope" section.
NETWORKS_WITH_REVERSAL_RISK = {"UPI_AUTOPAY"}


class PendingReversal:
    """One provisional 'success' that hasn't been finally confirmed yet."""

    __slots__ = ("transaction_id", "bank", "error_code", "network", "arm", "amount", "revenue_weight")

    def __init__(self, transaction_id, bank, error_code, network, arm, amount, revenue_weight):
        self.transaction_id = transaction_id
        self.bank = bank
        self.error_code = error_code
        self.network = network
        self.arm = arm
        self.amount = amount
        self.revenue_weight = revenue_weight


class ReversalTracker:
    """
    Tracks provisional "successes" and resolves them in an end-of-run
    correction pass. See module docstring for the real-world grounding
    and the disclosed scheduling simplification.
    """

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.pending = []  # list[PendingReversal]

    def maybe_flag_provisional(self, network, transaction_id, bank, error_code, arm, amount, revenue_weight):
        """
        Call this whenever a transaction is nominally successful. Returns
        True if this success is provisional (a real "deemed approved"
        state -- may still resolve to success, but isn't final yet) and
        records it for later resolution. Returns False if the success is
        immediately final (the common case -- most successes are not
        provisional, and networks outside NETWORKS_WITH_REVERSAL_RISK
        never enter this state at all).
        """
        if network not in NETWORKS_WITH_REVERSAL_RISK:
            return False
        if self.rng.random() >= PROVISIONAL_RATE:
            return False

        self.pending.append(PendingReversal(transaction_id, bank, error_code, network, arm, amount, revenue_weight))
        return True

    def resolve_all(self, bandit, rule_engine=None):
        """
        Resolves every pending provisional transaction: draws whether it
        ultimately reverses, and if so, claws back the revenue AND (if a
        bandit is provided) corrects its posterior. Pass bandit=None for
        contexts with no learning system to correct (e.g. the static
        baseline, which still experiences the same rail-level reversal
        phenomenon but has no posterior to fix).

        Returns a summary dict: {
            "total_provisional": int,
            "total_reversed": int,
            "revenue_clawed_back": int,
        }
        """
        total_reversed = 0
        revenue_clawed_back = 0

        for pending in self.pending:
            reversed_ = self.rng.random() < REVERSAL_RATE_GIVEN_PROVISIONAL
            if not reversed_:
                continue  # this provisional success is confirmed final -- no correction needed

            total_reversed += 1
            revenue_clawed_back += pending.amount

            if bandit is not None:
                self._undo_success_apply_failure(bandit, pending)

        return {
            "total_provisional": len(self.pending),
            "total_reversed": total_reversed,
            "revenue_clawed_back": revenue_clawed_back,
        }

    def _undo_success_apply_failure(self, bandit, pending: PendingReversal):
        """
        Removes the revenue_weight previously credited to alpha (both
        base and network pools) and applies it to beta instead -- i.e.
        converts what the bandit thought was a success into what it now
        knows was actually a failure, using the same weight it was
        originally credited with.
        """
        base_key = bandit._base_key(pending.bank, pending.error_code)
        base_posterior = bandit.base_posteriors[base_key][pending.arm]
        network_posterior = bandit.network_posteriors[pending.network][pending.arm]

        w = pending.revenue_weight
        # undo the success credit
        base_posterior[0] = max(0.5, base_posterior[0] - w)
        network_posterior[0] = max(0.5, network_posterior[0] - w)
        # apply the correct failure credit
        base_posterior[1] += w
        network_posterior[1] += w


if __name__ == "__main__":
    # smoke test: confirm provisional flagging + reversal resolution +
    # bandit correction all work end to end on a tiny synthetic case.
    from engine.bandit import SegmentedThompsonBandit

    random.seed(0)
    rng = random.Random(0)
    bandit = SegmentedThompsonBandit()
    tracker = ReversalTracker(rng)

    bank, error_code, network, arm = "HDFC", "timeout", "UPI_AUTOPAY", "retry_24h"

    before = bandit.get_posterior_mean(bank, error_code, network, arm)
    print(f"Posterior mean BEFORE any transactions: {before:.4f}")

    n_provisional = 0
    for i in range(500):  # enough volume to reliably see a few provisional/reversed cases
        txn_id = f"txn-{i}"
        is_provisional = tracker.maybe_flag_provisional(network, txn_id, bank, error_code, arm,
                                                           amount=999, revenue_weight=1.0)
        # every transaction is credited as a success immediately (as a
        # real system would react in real time, before knowing about any
        # future reversal)
        bandit.update(bank, error_code, network, arm, success=True, revenue_weight=1.0)
        if is_provisional:
            n_provisional += 1

    after_immediate = bandit.get_posterior_mean(bank, error_code, network, arm)
    print(f"Posterior mean AFTER 500 immediate 'successes' (before corrections): {after_immediate:.4f}")
    print(f"Flagged as provisional: {n_provisional} / 500")

    summary = tracker.resolve_all(bandit, rule_engine=None)
    print(f"\nResolution summary: {summary}")

    after_correction = bandit.get_posterior_mean(bank, error_code, network, arm)
    print(f"Posterior mean AFTER end-of-run corrections: {after_correction:.4f}")
    print(f"(should be slightly LOWER than the pre-correction value, since some 'successes' turned out fake)")