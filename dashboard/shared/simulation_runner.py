"""
simulation_runner.py

Shared, cached simulation utilities for every dashboard page. Bootstraps
the project root onto sys.path (so `from engine.xxx import ...` and
`from audit.audit_log import ...` work regardless of where `streamlit
run` is launched from), loads the synthetic dataset once, and wraps the
core simulation calls in st.cache_data so repeated UI interactions don't
recompute anything unnecessarily -- while a genuinely NEW seed always
triggers a real, fresh computation (since it's a different cache key).
"""

import sys
import random
from pathlib import Path

import streamlit as st

# --- path bootstrap: make engine/, data/, audit/ importable regardless
# of the working directory `streamlit run` was launched from ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
TRANSACTIONS_PATH = DATA_DIR / "transactions.csv"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"

from engine.simulator import (
    load_transactions,
    load_ground_truth,
    run_static_baseline,
    run_remultibands,
    simulate_outcome,
)
from engine.bandit import SegmentedThompsonBandit
from engine.priors import BANKS, ERROR_CODES, PAYMENT_NETWORKS  # re-exported for dashboard pages


@st.cache_data(show_spinner=False)
def load_dataset():
    """Loads the synthetic transactions + hidden ground truth once, cached for the whole session."""
    transactions = load_transactions(str(TRANSACTIONS_PATH))
    ground_truth = load_ground_truth(str(GROUND_TRUTH_PATH))
    return transactions, ground_truth


@st.cache_data(show_spinner="Running simulation...")
def run_comparison(seed: int):
    """
    Runs BOTH strategies for a given seed. Returns:
        (baseline_result, remultibands_result, audit_entries, audit_summary_text)
    audit_entries is a plain list of dicts (AuditLog.entries) -- easier
    to cache and hand to pandas than the AuditLog object itself.
    """
    transactions, ground_truth = load_dataset()

    baseline_result = run_static_baseline(transactions, ground_truth, random.Random(seed))
    remultibands_result, audit_log, _trained_bandit = run_remultibands(
        transactions, ground_truth, random.Random(seed)
    )

    return baseline_result, remultibands_result, audit_log.entries, audit_log.summary()


@st.cache_data(show_spinner="Running robustness sweep across 10 seeds...")
def run_robustness_sweep(seeds=tuple(range(1, 11))):
    """Runs the comparison across multiple seeds, returns a list of per-seed summary dicts."""
    transactions, ground_truth = load_dataset()
    rows = []
    for seed in seeds:
        baseline_result = run_static_baseline(transactions, ground_truth, random.Random(seed))
        remultibands_result, _, _ = run_remultibands(transactions, ground_truth, random.Random(seed))
        lift = remultibands_result["total_recovered"] - baseline_result["total_recovered"]
        lift_pct = (lift / baseline_result["total_recovered"]) * 100 if baseline_result["total_recovered"] else 0
        rows.append({
            "seed": seed,
            "baseline_recovered": baseline_result["total_recovered"],
            "remultibands_recovered": remultibands_result["total_recovered"],
            "lift": lift,
            "lift_pct": lift_pct,
            "baseline_strikes": baseline_result["network_strikes_incurred"],
            "remultibands_strikes": remultibands_result["network_strikes_incurred"],
        })
    return rows


def new_random_seed():
    """Generates a fresh random seed for the 'Run on New Seed' button."""
    return random.randint(1, 1_000_000)


@st.cache_data(show_spinner="Mapping trained beliefs across all segments...")
def get_bandit_snapshots(seed: int) -> dict:
    """
    Runs the full reMultiBands simulation for a given seed and returns the
    trained bandit's combined-probability belief for every
    (bank, error_code, network, arm) combination as a plain nested dict.

    Structure:
        { "BANK|ERROR|NETWORK": { "arm_name": combined_prob, ... }, ... }

    Plain floats only - fully serialisable for st.cache_data.
    """
    transactions, ground_truth = load_dataset()
    _, _, trained_bandit = run_remultibands(transactions, ground_truth, random.Random(seed))

    snapshots: dict = {}
    for bank in BANKS:
        for error_code in ERROR_CODES:
            for network in PAYMENT_NETWORKS:
                snap = trained_bandit.snapshot(bank, error_code, network)
                snapshots[f"{bank}|{error_code}|{network}"] = {
                    arm: round(float(data["combined_probability"]), 4)
                    for arm, data in snap.items()
                }
    return snapshots



@st.cache_data(show_spinner=False)
def run_segment_walkthrough(bank: str, error_code: str, network: str, n_steps: int, seed: int = 42):
    """
    Runs an isolated mini-simulation for ONE (bank, error_code, network)
    segment -- used by the "Watch It Learn" page. Feeds n_steps synthetic
    observations (drawn from the real hidden ground truth for this
    segment) through a FRESH bandit, recording a snapshot of its belief
    after every step, so the dashboard can plot how the posterior
    converges over time.
    """
    _, ground_truth = load_dataset()
    rng = random.Random(seed)

    bandit = SegmentedThompsonBandit()
    history = []

    for step in range(1, n_steps + 1):
        arm, _sampled_values = bandit.select_arm(bank, error_code, network)
        success = simulate_outcome(ground_truth, bank, error_code, network, arm, rng)
        bandit.update(bank, error_code, network, arm, success, revenue_weight=1.0)

        snapshot = bandit.snapshot(bank, error_code, network)
        history.append({
            "step": step,
            "arm_chosen": arm,
            "success": success,
            "beliefs": {a: snapshot[a]["combined_probability"] for a in snapshot},
        })

    return history