"""
generate_data.py

Generates a synthetic dataset of failed payment/mandate transactions for
the reMultiBands demo, PLUS a hidden "ground truth" table of success
probabilities per (bank, error_code, arm).

Important design choice:
    The ground truth table is intentionally NOT visible to the bandit engine.
    It lives in ground_truth.json purely so the simulator can decide, at
    run time, whether a given recovery action (arm) succeeds for a given
    transaction. The bandit only ever sees observed outcomes (success/fail)
    fed back to it after it picks an arm -- exactly like a production
    system would only observe real retry outcomes, never the underlying
    probability.

Retry caps are RESEARCH-GROUNDED, not invented, and vary by payment
network + decline category (see NETWORK_RETRY_CAPS and
HARD_DECLINE_ERROR_CODES below for sources).

Run:
    python generate_data.py
Outputs:
    transactions.csv   -- the failed transactions to replay through the sim
    ground_truth.json  -- hidden success-probability table + retry caps (sim-only)
"""

import csv
import json
import random
import uuid
from datetime import datetime, timedelta

random.seed(42)  # reproducible demo run

BANKS = ["HDFC", "SBI", "ICICI", "Axis", "Kotak"]
ERROR_CODES = ["timeout", "insufficient_funds", "hard_decline", "issuer_unavailable"]
ARMS = ["retry_2h", "retry_24h", "retry_72h", "whatsapp_escalate"]

# error codes that represent a PERMANENT decline (card lost/stolen/closed,
# account doesn't exist) rather than a temporary/recoverable one.
HARD_DECLINE_ERROR_CODES = {"hard_decline"}

N_TRANSACTIONS = 9500

# -----------------------------------------------------------------------
# Payment network / rail per transaction, and the RETRY CAP that actually
# applies to it. These are grounded in published rules, not invented:
#
#   - UPI_AUTOPAY: NPCI's August 2025 Autopay guidelines standardize
#     retries to "1 original attempt + up to 3 retries" per mandate
#     execution cycle. Source: multiple 2026 fintech/payments blogs
#     (incl. Razorpay's own blog) citing the NPCI circular.
#   - Visa: the "Excessive Reattempts Rule" permits up to 15 reattempts
#     within a rolling 30-day window for RETRY-ELIGIBLE (soft) declines.
#     Hard declines (Category 1 -- lost/stolen/closed card) get ZERO
#     permitted reattempts; retrying one is an automatic violation.
#   - Mastercard: stricter than Visa, commonly cited around 10 retries
#     in 30 days. Mastercard doesn't publish one single universal number
#     the way Visa does -- it signals per-transaction via Merchant
#     Advice Codes (MAC 03 = do not retry at all, MACs 24-30 = specific
#     wait windows). We use 10 as a reasonable, commonly-cited ceiling.
#   - RuPay: NO separately published RuPay-specific numeric cap was
#     found in research. Since NPCI governs RuPay (as it does UPI), we
#     conservatively apply the same NPCI/UPI-style cap as a placeholder
#     assumption -- this should be confirmed against the actual RuPay
#     scheme rules / acquirer agreement in a real production system.
#
# CRITICAL NUANCE: hard declines get ZERO retries on ANY network,
# regardless of the network's normal cap -- see HARD_DECLINE_ERROR_CODES
# and get_retry_cap() below. This mirrors Visa's published Category 1
# rule and is applied uniformly across all networks in this model as a
# conservative, defensible default.
# -----------------------------------------------------------------------

PAYMENT_NETWORKS = ["UPI_AUTOPAY", "RuPay", "Visa", "Mastercard"]

# India-weighted: UPI Autopay dominant in Indian recurring/subscription
# volume, RuPay second (domestic card scheme), Visa/Mastercard smaller
# share for this kind of merchant. Illustrative weighting, not sourced.
PAYMENT_NETWORK_WEIGHTS = {
    "UPI_AUTOPAY": 0.45,
    "RuPay": 0.20,
    "Visa": 0.20,
    "Mastercard": 0.15,
}

NETWORK_RETRY_CAPS = {
    "UPI_AUTOPAY": 3,   # NPCI Aug 2025: 1 original + 3 retries -> 3 retries after the initial failure
    "RuPay": 3,         # ASSUMPTION -- no distinct published cap found, mirrors NPCI/UPI Autopay
    "Visa": 15,         # Visa Excessive Reattempts Rule -- soft declines only
    "Mastercard": 10,   # Commonly cited ceiling -- Mastercard signals per-txn via Merchant Advice Codes
}


def get_retry_cap(network, error_code):
    """
    Returns the actual retry cap for a given (network, error_code)
    combination. Hard declines get 0 on every network (see module
    docstring); otherwise the network's published/assumed cap applies.
    """
    if error_code in HARD_DECLINE_ERROR_CODES:
        return 0
    return NETWORK_RETRY_CAPS.get(network, 3)  # 3 as a conservative fallback if network is unrecognized


# -----------------------------------------------------------------------
# Hidden ground-truth success probabilities per (bank, error_code, arm).
# These are DELIBERATELY biased so the bandit has real, discoverable
# structure to learn during the demo. whatsapp_escalate is intentionally
# a reliable-but-not-perfect fallback across all segments (a human paying
# via a link works reasonably often regardless of *why* the original
# charge failed).
# -----------------------------------------------------------------------

BASE_WHATSAPP_SUCCESS = 0.55  # roughly segment-independent baseline

# hand-authored biases: (bank, error_code) -> {arm: success_prob}
GROUND_TRUTH = {
    ("HDFC", "timeout"): {
        "retry_2h": 0.05,   # HDFC gateway still hot/congested at 2h -> fails almost always
        "retry_24h": 0.85,  # by 24h HDFC's gateway has recovered -> strong recovery
        "retry_72h": 0.55,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("HDFC", "insufficient_funds"): {
        "retry_2h": 0.03,
        "retry_24h": 0.10,
        "retry_72h": 0.65,  # salary/payday cycle -> waiting longer pays off
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("HDFC", "hard_decline"): {
        "retry_2h": 0.01,
        "retry_24h": 0.02,
        "retry_72h": 0.02,  # hard declines basically never self-resolve via retry
        "whatsapp_escalate": 0.60,  # escalation is clearly the right move
    },
    ("HDFC", "issuer_unavailable"): {
        "retry_2h": 0.40,  # short-lived issuer blips -> quick retry often works
        "retry_24h": 0.30,
        "retry_72h": 0.25,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("SBI", "timeout"): {
        "retry_2h": 0.10,
        "retry_24h": 0.35,
        "retry_72h": 0.70,  # SBI recovers slower than HDFC -> needs longer window
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("SBI", "insufficient_funds"): {
        "retry_2h": 0.02,
        "retry_24h": 0.08,
        "retry_72h": 0.72,  # strongest payday-cycle effect in the dataset
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("SBI", "hard_decline"): {
        "retry_2h": 0.01,
        "retry_24h": 0.01,
        "retry_72h": 0.01,
        "whatsapp_escalate": 0.58,
    },
    ("SBI", "issuer_unavailable"): {
        "retry_2h": 0.45,
        "retry_24h": 0.25,
        "retry_72h": 0.20,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("ICICI", "timeout"): {
        "retry_2h": 0.15,
        "retry_24h": 0.60,
        "retry_72h": 0.50,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("ICICI", "insufficient_funds"): {
        "retry_2h": 0.03,
        "retry_24h": 0.12,
        "retry_72h": 0.68,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("ICICI", "hard_decline"): {
        "retry_2h": 0.01,
        "retry_24h": 0.02,
        "retry_72h": 0.01,
        "whatsapp_escalate": 0.62,
    },
    ("ICICI", "issuer_unavailable"): {
        "retry_2h": 0.50,
        "retry_24h": 0.28,
        "retry_72h": 0.22,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("Axis", "timeout"): {
        "retry_2h": 0.08,
        "retry_24h": 0.75,
        "retry_72h": 0.45,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("Axis", "insufficient_funds"): {
        "retry_2h": 0.02,
        "retry_24h": 0.09,
        "retry_72h": 0.60,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("Axis", "hard_decline"): {
        "retry_2h": 0.01,
        "retry_24h": 0.01,
        "retry_72h": 0.02,
        "whatsapp_escalate": 0.57,
    },
    ("Axis", "issuer_unavailable"): {
        "retry_2h": 0.42,
        "retry_24h": 0.27,
        "retry_72h": 0.18,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("Kotak", "timeout"): {
        "retry_2h": 0.12,
        "retry_24h": 0.55,
        "retry_72h": 0.48,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("Kotak", "insufficient_funds"): {
        "retry_2h": 0.02,
        "retry_24h": 0.11,
        "retry_72h": 0.63,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
    ("Kotak", "hard_decline"): {
        "retry_2h": 0.01,
        "retry_24h": 0.02,
        "retry_72h": 0.01,
        "whatsapp_escalate": 0.59,
    },
    ("Kotak", "issuer_unavailable"): {
        "retry_2h": 0.38,
        "retry_24h": 0.24,
        "retry_72h": 0.19,
        "whatsapp_escalate": BASE_WHATSAPP_SUCCESS,
    },
}

# roughly realistic-ish skew: insufficient_funds and timeout are most common
ERROR_CODE_WEIGHTS = {
    "timeout": 0.35,
    "insufficient_funds": 0.30,
    "issuer_unavailable": 0.20,
    "hard_decline": 0.15,
}

# amount distribution (INR), log-ish spread typical of subscription/mandate charges
AMOUNT_BUCKETS = [199, 299, 499, 999, 1499, 2999, 4999]


def weighted_choice(options_with_weights: dict):
    options = list(options_with_weights.keys())
    weights = list(options_with_weights.values())
    return random.choices(options, weights=weights, k=1)[0]


# -----------------------------------------------------------------------
# Network-level modifiers, layered on top of the hand-authored (bank,
# error_code) base probabilities above, so the bandit has real,
# network-specific structure to discover (not just bank/error structure).
# These are ILLUSTRATIVE, not sourced from real data -- directional
# reasoning only:
#   - UPI_AUTOPAY: a real-time push rail with fast user notifications --
#     quick retries do relatively better, long waits relatively worse,
#     and WhatsApp escalation converts especially well (same mobile-first
#     audience already comfortable with UPI notification flows).
#   - RuPay: treated as the neutral baseline (no modifier) -- closest
#     analog to how the base GROUND_TRUTH table above was authored.
#   - Visa / Mastercard: international card rails -- slightly worse on
#     very quick retries, slightly better once given a full day (24h) to
#     clear, and slightly worse on WhatsApp escalation (card-only
#     customers are somewhat less likely to already be in a WhatsApp
#     flow with the merchant).
# -----------------------------------------------------------------------

NETWORK_MODIFIERS = {
    "UPI_AUTOPAY": {"retry_2h": 0.04, "retry_24h": 0.00, "retry_72h": -0.04, "whatsapp_escalate": 0.06},
    "RuPay": {"retry_2h": 0.00, "retry_24h": 0.00, "retry_72h": 0.00, "whatsapp_escalate": 0.00},
    "Visa": {"retry_2h": -0.03, "retry_24h": 0.04, "retry_72h": 0.01, "whatsapp_escalate": -0.05},
    "Mastercard": {"retry_2h": -0.02, "retry_24h": 0.03, "retry_72h": 0.01, "whatsapp_escalate": -0.03},
}


def apply_network_modifier(base_prob, network, arm):
    delta = NETWORK_MODIFIERS.get(network, {}).get(arm, 0.0)
    return min(0.98, max(0.01, base_prob + delta))


def build_expanded_ground_truth():
    """
    Expands the hand-authored (bank, error_code) -> {arm: prob} table
    above into the FULL (bank, error_code, network) -> {arm: prob} table
    actually used by the simulator, by layering NETWORK_MODIFIERS on top
    of each base probability. Returns a dict keyed
    "bank|error_code|payment_network" -> {arm: prob}.
    """
    expanded = {}
    for (bank, error_code), arm_probs in GROUND_TRUTH.items():
        for network in PAYMENT_NETWORKS:
            key = f"{bank}|{error_code}|{network}"
            expanded[key] = {
                arm: apply_network_modifier(prob, network, arm)
                for arm, prob in arm_probs.items()
            }
    return expanded


def generate_transactions(n=N_TRANSACTIONS):
    transactions = []
    start = datetime(2026, 8, 1, 9, 0, 0)

    for i in range(n):
        bank = random.choice(BANKS)
        error_code = weighted_choice(ERROR_CODE_WEIGHTS)
        payment_network = weighted_choice(PAYMENT_NETWORK_WEIGHTS)
        amount = random.choice(AMOUNT_BUCKETS)
        failed_at = start + timedelta(minutes=random.randint(0, 60 * 24 * 20))  # spread over ~20 days

        transactions.append(
            {
                "transaction_id": str(uuid.uuid4())[:8],
                "bank": bank,
                "error_code": error_code,
                "payment_network": payment_network,
                "amount_inr": amount,
                "failed_at": failed_at.isoformat(),
            }
        )

    # keep chronological order, like a real event stream
    transactions.sort(key=lambda t: t["failed_at"])
    return transactions


def save_transactions(transactions, path="transactions.csv"):
    fieldnames = ["transaction_id", "bank", "error_code", "payment_network", "amount_inr", "failed_at"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transactions)


def save_ground_truth(path="ground_truth.json"):
    expanded = build_expanded_ground_truth()
    with open(path, "w") as f:
        json.dump(
            {
                "arms": ARMS,
                "payment_networks": PAYMENT_NETWORKS,
                "network_retry_caps": NETWORK_RETRY_CAPS,
                "hard_decline_error_codes": list(HARD_DECLINE_ERROR_CODES),
                "segment_key_format": "bank|error_code|payment_network",
                "probabilities": expanded,
            },
            f,
            indent=2,
        )


if __name__ == "__main__":
    txns = generate_transactions()
    save_transactions(txns)
    save_ground_truth()
    expanded = build_expanded_ground_truth()
    print(f"Generated {len(txns)} synthetic failed transactions -> transactions.csv")
    print(f"Wrote hidden ground-truth success table -> ground_truth.json")
    print(f"Fine segments covered: {len(expanded)} (bank x error_code x payment_network combinations)")
    print(f"Payment networks: {PAYMENT_NETWORKS}")
    print(f"Retry caps by network: {NETWORK_RETRY_CAPS}")
    print(f"Hard decline error codes (always 0 retries, any network): {HARD_DECLINE_ERROR_CODES}")