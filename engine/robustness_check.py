"""
robustness_check.py

Runs the full simulator.py comparison across several different random
seeds and reports whether the core claims hold up EVERY time, not just
for one lucky/unlucky seed.

This does NOT regenerate transactions.csv or ground_truth.json -- the
transaction list and the hidden ground-truth probabilities stay fixed
(that's the "world" being simulated). What changes across seeds is only
the actual coin-flip outcomes drawn from those probabilities each run --
i.e. we're checking "does the bandit reliably win against this world,
across many different possible unfoldings of chance," not "did we pick a
suspiciously friendly world."

Run:
    python -m engine.robustness_check
"""

import random

from engine.simulator import (
    load_transactions,
    load_ground_truth,
    run_static_baseline,
    run_remultibands,
)

SEEDS_TO_TEST = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


def run_robustness_check():
    transactions = load_transactions()
    ground_truth = load_ground_truth()

    print(f"Running {len(SEEDS_TO_TEST)} independent seeds over {len(transactions)} transactions...\n")
    print(f"{'Seed':<6}{'Baseline Rs.':>14}{'reMultiBands Rs.':>18}{'Lift Rs.':>12}{'Lift %':>9}"
          f"{'Base Strikes':>14}{'RMB Strikes':>13}")
    print("-" * 90)

    lifts = []
    lift_pcts = []
    all_zero_strikes = True

    for seed in SEEDS_TO_TEST:
        baseline_result = run_static_baseline(transactions, ground_truth, random.Random(seed))
        remultibands_result, _, _ = run_remultibands(transactions, ground_truth, random.Random(seed))

        lift = remultibands_result["total_recovered"] - baseline_result["total_recovered"]
        lift_pct = (lift / baseline_result["total_recovered"]) * 100
        lifts.append(lift)
        lift_pcts.append(lift_pct)

        rmb_strikes = remultibands_result["network_strikes_incurred"]
        if rmb_strikes != 0:
            all_zero_strikes = False

        print(
            f"{seed:<6}{baseline_result['total_recovered']:>14,}"
            f"{remultibands_result['total_recovered']:>18,}"
            f"{lift:>12,}{lift_pct:>8.1f}%"
            f"{baseline_result['network_strikes_incurred']:>14,}"
            f"{rmb_strikes:>13,}"
        )

    print("-" * 90)
    avg_lift = sum(lifts) / len(lifts)
    avg_lift_pct = sum(lift_pcts) / len(lift_pcts)
    min_lift = min(lifts)
    max_lift = max(lifts)

    print(f"\nAverage lift across {len(SEEDS_TO_TEST)} seeds: Rs.{avg_lift:,.0f} ({avg_lift_pct:.1f}%)")
    print(f"Lift range: Rs.{min_lift:,} to Rs.{max_lift:,}")
    print(f"reMultiBands beat the baseline in {sum(1 for l in lifts if l > 0)}/{len(lifts)} seeds")
    print(f"reMultiBands incurred ZERO network strikes in "
          f"{'ALL' if all_zero_strikes else 'NOT ALL'} {len(SEEDS_TO_TEST)} seeds")

    if all_zero_strikes and all(l > 0 for l in lifts):
        print("\n-> Result is ROBUST: reMultiBands wins on both revenue and compliance across every tested seed.")
    else:
        print("\n-> WARNING: result is NOT consistent across all seeds -- investigate before using in the pitch.")


if __name__ == "__main__":
    run_robustness_check()