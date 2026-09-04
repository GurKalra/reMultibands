"""
simulator.py

Runs the full reMultiBands demo: replays the synthetic failed-transaction
dataset through TWO parallel recovery strategies and compares them.

    1. STATIC BASELINE -- the naive status quo. Every failed transaction
       is retried on a fixed schedule (always retry_24h), with no
       awareness of bank/error_code/payment_network, no rule engine, and
       NO knowledge that different rails/decline types carry different
       (and sometimes very strict) retry caps. It keeps retrying up to
       MAX_STATIC_ATTEMPTS times regardless of compliance -- any attempt
       beyond the ACTUAL applicable cap for that transaction's network +
       decline type is counted as a network strike incurred. This is a
       SIMULATED counterfactual on synthetic data only -- nothing here
       touches a real bank or network.

    2. reMultiBands -- the segmented Thompson Sampling bandit + rule
       engine we built. Each transaction is decided one attempt at a
       time: the rule engine looks up the REAL applicable cap for this
       transaction's (payment_network, error_code) -- see
       engine/rule_engine.py for the research behind these caps -- and
       either lets the bandit choose freely, narrows its choices in the
       "soft zone" near the cap, or force-overrides to whatsapp_escalate
       once the cap is reached. The outcome is drawn from the HIDDEN
       ground-truth table, the posterior updates, and the loop repeats
       until the transaction resolves (success) or escalates.

Both strategies also experience DELAYED/REVERSED "deemed approved"
outcomes on UPI_AUTOPAY (see engine/reversal_model.py) -- a real,
RBI-regulated phenomenon where a nominal "success" isn't always final,
and can silently reverse days later. This is applied to BOTH strategies
equally, since it's a property of the payment rail, not of which
recovery strategy is used -- applying it only to reMultiBands would
unfairly bias the comparison.

Every reMultiBands decision is recorded in a real AuditLog (see
audit/audit_log.py) -- not just a throwaway list. AuditLog is not used
for the static baseline: it has no bandit source, no excluded-arms
concept, and no rule-engine override distinction to explain, so its
schema doesn't meaningfully apply there. The audit trail is specifically
proof of reMultiBands' compliant, explainable decision-making.

This file is the "proof" behind the pitch: it produces the numbers for
the side-by-side dashboard (Total Recovered, Network Strikes, Escalations
Triggered).
"""

import csv
import json
import random

from engine.bandit import SegmentedThompsonBandit
from engine.rule_engine import RuleEngine, ESCALATION_ARM, AVERAGE_TRANSACTION_AMOUNT
from engine.reversal_model import ReversalTracker
from audit.audit_log import AuditLog

MAX_STATIC_ATTEMPTS = 6  # how many times the naive baseline blindly retries before giving up


def load_transactions(path="data/transactions.csv"):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_ground_truth(path="data/ground_truth.json"):
    with open(path) as f:
        return json.load(f)


def simulate_outcome(ground_truth, bank, error_code, network, arm, rng):
    """Draws a success/fail outcome for one (bank, error_code, network, arm) using the hidden probability table."""
    key = f"{bank}|{error_code}|{network}"
    prob = ground_truth["probabilities"][key][arm]
    return rng.random() < prob


def get_applicable_cap(ground_truth, network, error_code):
    """
    Shared cap lookup used by BOTH the static baseline (to measure
    violations against the real limit) and RuleEngine (to enforce it).
    Hard declines get 0 on every network -- see engine/rule_engine.py's
    module docstring for the research behind this.
    """
    if error_code in ground_truth["hard_decline_error_codes"]:
        return 0
    return ground_truth["network_retry_caps"].get(network, 3)


def run_static_baseline(transactions, ground_truth, rng):
    """
    Naive status quo: always retry_24h, on a fixed schedule, no
    awareness of bank/error_code/payment_network, no escalation channel,
    no idea that different rails/decline types carry different (and
    sometimes very strict, e.g. UPI Autopay's 3-retry cap) limits. Keeps
    going until success or MAX_STATIC_ATTEMPTS attempts are exhausted.

    Also experiences delayed/reversed UPI_AUTOPAY outcomes (see
    engine/reversal_model.py) for a fair comparison against reMultiBands.
    """
    total_recovered = 0
    total_unrecovered = 0
    total_attempts = 0
    network_strikes_incurred = 0
    resolved_count = 0

    reversal_tracker = ReversalTracker(rng)

    for txn in transactions:
        txn_id = txn["transaction_id"]
        bank = txn["bank"]
        error_code = txn["error_code"]
        network = txn["payment_network"]
        amount = int(txn["amount_inr"])

        applicable_cap = get_applicable_cap(ground_truth, network, error_code)

        resolved = False
        for attempt_num in range(1, MAX_STATIC_ATTEMPTS + 1):
            total_attempts += 1

            # any attempt beyond the REAL applicable cap for this
            # transaction's network+decline-type is a compliance
            # violation -- the baseline has no idea this cap exists (or
            # that it varies by rail), so it just keeps going anyway
            if attempt_num > applicable_cap:
                network_strikes_incurred += 1

            success = simulate_outcome(ground_truth, bank, error_code, network, "retry_24h", rng)
            if success:
                total_recovered += amount
                resolved = True
                resolved_count += 1
                reversal_tracker.maybe_flag_provisional(
                    network, txn_id, bank, error_code, "retry_24h", amount,
                    revenue_weight=amount / AVERAGE_TRANSACTION_AMOUNT,
                )
                break

        if not resolved:
            total_unrecovered += amount

    # end-of-run correction pass: some nominal "successes" above were
    # only provisional and are now confirmed to have reversed
    reversal_summary = reversal_tracker.resolve_all(bandit=None)
    gross_recovered = total_recovered
    total_recovered -= reversal_summary["revenue_clawed_back"]
    total_unrecovered += reversal_summary["revenue_clawed_back"]

    return {
        "strategy": "static_baseline",
        "total_recovered": total_recovered,
        "gross_recovered_before_reversals": gross_recovered,
        "total_unrecovered": total_unrecovered,
        "resolved_count": resolved_count,
        "total_transactions": len(transactions),
        "total_attempts": total_attempts,
        "network_strikes_incurred": network_strikes_incurred,
        "escalations_triggered": 0,  # baseline has no escalation channel
        "total_provisional_transactions": reversal_summary["total_provisional"],
        "total_reversed_transactions": reversal_summary["total_reversed"],
        "revenue_clawed_back_by_reversals": reversal_summary["revenue_clawed_back"],
    }


def run_remultibands(transactions, ground_truth, rng):
    """
    reMultiBands: segmented Thompson Sampling bandit, wrapped by the
    deterministic rule engine that looks up the REAL applicable cap per
    transaction (network + decline type), narrows choices in the soft
    zone near that cap, and hard-stops at the cap by escalating to
    WhatsApp instead of ever violating it.

    Also experiences delayed/reversed UPI_AUTOPAY outcomes (see
    engine/reversal_model.py): every nominal success is credited
    immediately (as a real system reacts in real time), but a fraction
    are provisional and get corrected -- both in revenue totals AND in
    the bandit's learned posterior -- in an end-of-run pass.
    """
    bandit = SegmentedThompsonBandit()
    rule_engine = RuleEngine(bandit, network_retry_caps=ground_truth["network_retry_caps"],
                              hard_decline_error_codes=ground_truth["hard_decline_error_codes"])
    reversal_tracker = ReversalTracker(rng)
    audit_log = AuditLog()

    total_recovered = 0
    total_unrecovered = 0
    total_attempts = 0
    network_strikes_incurred = 0  # should stay at 0 -- rule engine prevents this by design
    escalations_triggered = 0
    resolved_count = 0

    for txn in transactions:
        txn_id = txn["transaction_id"]
        bank = txn["bank"]
        error_code = txn["error_code"]
        network = txn["payment_network"]
        amount = int(txn["amount_inr"])

        resolved = False
        while not resolved:
            decision = rule_engine.decide(txn_id, bank, error_code, network)
            arm = decision["arm"]
            total_attempts += 1

            success = simulate_outcome(ground_truth, bank, error_code, network, arm, rng)
            rule_engine.record_outcome(txn_id, bank, error_code, network, arm, success, amount=amount)

            audit_log.log_decision(txn_id, bank, error_code, network, amount, decision, success)

            if arm == ESCALATION_ARM:
                escalations_triggered += 1
                if success:
                    total_recovered += amount
                    resolved_count += 1
                    reversal_tracker.maybe_flag_provisional(
                        network, txn_id, bank, error_code, arm, amount,
                        revenue_weight=amount / AVERAGE_TRANSACTION_AMOUNT,
                    )
                else:
                    total_unrecovered += amount
                resolved = True  # sequence always ends at escalation, win or lose
            elif success:
                total_recovered += amount
                resolved_count += 1
                reversal_tracker.maybe_flag_provisional(
                    network, txn_id, bank, error_code, arm, amount,
                    revenue_weight=amount / AVERAGE_TRANSACTION_AMOUNT,
                )
                resolved = True
            # else: failed API retry, loop continues -- rule_engine will
            # force escalation once the applicable cap is hit, so this
            # never spins forever

        # network strikes should NEVER fire for reMultiBands by design --
        # kept here only as a runtime sanity check / verification
        applicable_cap = get_applicable_cap(ground_truth, network, error_code)
        attempts_for_txn = rule_engine.attempts_used.get(txn_id, 0)
        if attempts_for_txn > applicable_cap:
            network_strikes_incurred += 1  # should never happen

    # end-of-run correction pass: some nominal "successes" above were
    # only provisional and are now confirmed to have reversed -- correct
    # BOTH the revenue totals AND the bandit's posterior
    reversal_summary = reversal_tracker.resolve_all(bandit)
    gross_recovered = total_recovered
    total_recovered -= reversal_summary["revenue_clawed_back"]
    total_unrecovered += reversal_summary["revenue_clawed_back"]

    result = {
        "strategy": "remultibands",
        "total_recovered": total_recovered,
        "gross_recovered_before_reversals": gross_recovered,
        "total_unrecovered": total_unrecovered,
        "resolved_count": resolved_count,
        "total_transactions": len(transactions),
        "total_attempts": total_attempts,
        "network_strikes_incurred": network_strikes_incurred,
        "escalations_triggered": escalations_triggered,
        "total_provisional_transactions": reversal_summary["total_provisional"],
        "total_reversed_transactions": reversal_summary["total_reversed"],
        "revenue_clawed_back_by_reversals": reversal_summary["revenue_clawed_back"],
    }
    return result, audit_log, bandit


def print_comparison(baseline_result, remultibands_result):
    print("=" * 70)
    print(f"{'Metric':<32}{'Static Baseline':>18}{'reMultiBands':>18}")
    print("=" * 70)

    rows = [
        ("Total Recovered (INR, net)", baseline_result["total_recovered"], remultibands_result["total_recovered"]),
        ("Total Unrecovered (INR)", baseline_result["total_unrecovered"], remultibands_result["total_unrecovered"]),
        ("Transactions Resolved", baseline_result["resolved_count"], remultibands_result["resolved_count"]),
        ("Total Attempts Made", baseline_result["total_attempts"], remultibands_result["total_attempts"]),
        ("Network Strikes Incurred", baseline_result["network_strikes_incurred"], remultibands_result["network_strikes_incurred"]),
        ("Escalations Triggered", baseline_result["escalations_triggered"], remultibands_result["escalations_triggered"]),
        ("Provisional (UPI deemed-approved)", baseline_result["total_provisional_transactions"], remultibands_result["total_provisional_transactions"]),
        ("...of which later Reversed", baseline_result["total_reversed_transactions"], remultibands_result["total_reversed_transactions"]),
        ("Revenue Clawed Back (INR)", baseline_result["revenue_clawed_back_by_reversals"], remultibands_result["revenue_clawed_back_by_reversals"]),
    ]

    for label, base_val, rmb_val in rows:
        print(f"{label:<32}{base_val:>18,}{rmb_val:>18,}")

    print("=" * 70)
    recovery_lift = remultibands_result["total_recovered"] - baseline_result["total_recovered"]
    print(f"\nreMultiBands recovered Rs.{recovery_lift:,} more than the static baseline (net of reversals),")
    print(f"while incurring {remultibands_result['network_strikes_incurred']} network strikes "
          f"vs baseline's {baseline_result['network_strikes_incurred']}.")


if __name__ == "__main__":
    transactions = load_transactions()
    ground_truth = load_ground_truth()

    print(f"Loaded {len(transactions)} failed transactions.\n")

    baseline_result = run_static_baseline(transactions, ground_truth, random.Random(7))
    remultibands_result, audit_log, trained_bandit = run_remultibands(
        transactions, ground_truth, random.Random(7)
    )

    print_comparison(baseline_result, remultibands_result)

    print(f"\n{'-' * 70}\n")
    print(audit_log.summary())

    audit_log.to_json("audit/decisions.json")
    print(f"\nWrote {len(audit_log.entries)} decisions -> audit/decisions.json (dashboard reads from here)")