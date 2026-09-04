"""
audit_log.py

Structured, human-readable audit trail for every recovery decision
reMultiBands makes. This is the direct answer to the track's bar:

    "...with compliant escalation, stopping rules, and an audit trail."

A decision by itself (arm="whatsapp_escalate") doesn't prove anything to
a judge or a compliance reviewer. What proves it is WHY -- was this the
bandit's own learned choice, or a hard rule-engine override? Was an arm
excluded because we were in the "soft zone"? What was the applicable
cap for this specific network + decline type? This module captures all
of that per decision, in a form that's both machine-readable (JSON, for
the dashboard) and human-readable (an explanation string, for a person
to actually read).

Usage:
    audit_log = AuditLog()
    ... inside the recovery loop, after rule_engine.decide() ...
    audit_log.log_decision(transaction_id, bank, error_code, network,
                            amount, decision_dict, success)
    ...
    audit_log.to_json("audit/decisions.json")
    print(audit_log.summary())
"""

import json


class AuditLog:
    def __init__(self):
        self.entries = []

    def log_decision(self, transaction_id, bank, error_code, network, amount, decision, success):
        """
        decision: the dict returned by RuleEngine.decide(), i.e.
            {
                "arm": ..., "source": ..., "attempts_used_before": ...,
                "attempts_remaining": ..., "applicable_cap": ...,
                "excluded_arms": ..., "sampled_values": ...,
            }
        success: the observed outcome of taking that arm (bool).
        """
        entry = {
            "transaction_id": transaction_id,
            "bank": bank,
            "error_code": error_code,
            "payment_network": network,
            "amount_inr": amount,
            "arm_chosen": decision["arm"],
            "decision_source": decision["source"],  # "bandit" | "rule_engine_override"
            "attempts_used_before": decision["attempts_used_before"],
            "attempts_remaining": decision["attempts_remaining"],
            "applicable_cap": decision["applicable_cap"],
            "excluded_arms": decision["excluded_arms"],
            "sampled_values": decision["sampled_values"],  # None if overridden
            "outcome_success": success,
            "explanation": self._explain(transaction_id, bank, error_code, network, decision, success),
        }
        self.entries.append(entry)
        return entry

    def _explain(self, transaction_id, bank, error_code, network, decision, success):
        """Builds a one-line, human-readable explanation of this decision."""
        attempt_number = decision["attempts_used_before"] + 1
        cap = decision["applicable_cap"]
        arm = decision["arm"]
        outcome_str = "succeeded" if success else "failed"

        if decision["source"] == "rule_engine_override":
            if cap == 0:
                reason = f"hard decline on {network} -> 0 retries permitted, escalated immediately"
            else:
                reason = f"attempt {attempt_number} would exceed the {cap}-retry cap for {network} -> forced escalation"
            return (
                f"Txn {transaction_id} ({bank}, {error_code}, {network}): "
                f"RULE ENGINE OVERRIDE -- {reason}. Outcome: {outcome_str}."
            )

        # bandit-driven decision
        excluded_note = ""
        if decision["excluded_arms"]:
            excluded_note = f" [rule engine excluded {decision['excluded_arms']} -- last attempt before cap]"

        posterior_note = ""
        if decision["sampled_values"]:
            sampled_for_chosen = decision["sampled_values"].get(arm)
            if sampled_for_chosen is not None:
                posterior_note = f" (sampled value {sampled_for_chosen:.3f})"

        return (
            f"Txn {transaction_id} ({bank}, {error_code}, {network}): "
            f"attempt {attempt_number}/{cap}, bandit chose {arm}{posterior_note}{excluded_note}. "
            f"Outcome: {outcome_str}."
        )

    def to_json(self, path):
        with open(path, "w") as f:
            json.dump(self.entries, f, indent=2)

    def summary(self):
        """
        Aggregate compliance/decision stats -- the numbers that back up
        the "compliant escalation + stopping rules" claim with more than
        just "zero strikes" (an absence). Shows the split between the
        bandit's own proactive choices and the rule engine's hard
        interventions, broken down by network.
        """
        total = len(self.entries)
        if total == 0:
            return "No decisions logged."

        bandit_count = sum(1 for e in self.entries if e["decision_source"] == "bandit")
        override_count = total - bandit_count

        soft_zone_count = sum(1 for e in self.entries if e["excluded_arms"])

        by_network = {}
        for e in self.entries:
            net = e["payment_network"]
            by_network.setdefault(net, {"bandit": 0, "rule_engine_override": 0})
            by_network[net][e["decision_source"]] += 1

        lines = [
            f"Total decisions logged: {total:,}",
            f"  Bandit-chosen: {bandit_count:,} ({bandit_count/total*100:.1f}%)",
            f"  Rule-engine overrides: {override_count:,} ({override_count/total*100:.1f}%)",
            f"  Soft-zone interventions (retry_72h excluded): {soft_zone_count:,}",
            "",
            "By payment network:",
        ]
        for net, counts in sorted(by_network.items()):
            net_total = counts["bandit"] + counts["rule_engine_override"]
            lines.append(
                f"  {net:<14} bandit={counts['bandit']:>5,}  "
                f"override={counts['rule_engine_override']:>5,}  "
                f"total={net_total:>5,}"
            )

        return "\n".join(lines)


if __name__ == "__main__":
    # smoke test: run a small slice of the real simulator and confirm the
    # audit log captures decisions with sensible explanations.
    from engine.simulator import load_transactions, load_ground_truth, simulate_outcome
    from engine.bandit import SegmentedThompsonBandit
    from engine.rule_engine import RuleEngine, ESCALATION_ARM
    import random

    transactions = load_transactions()[:50]  # small slice for a readable smoke test
    ground_truth = load_ground_truth()
    rng = random.Random(7)

    bandit = SegmentedThompsonBandit()
    rule_engine = RuleEngine(bandit, network_retry_caps=ground_truth["network_retry_caps"],
                              hard_decline_error_codes=ground_truth["hard_decline_error_codes"])
    audit_log = AuditLog()

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
            success = simulate_outcome(ground_truth, bank, error_code, arm, rng)
            rule_engine.record_outcome(txn_id, bank, error_code, network, arm, success, amount=amount)

            audit_log.log_decision(txn_id, bank, error_code, network, amount, decision, success)

            if arm == ESCALATION_ARM or success:
                resolved = True

    print("Sample explanations (first 8 decisions):\n")
    for entry in audit_log.entries[:8]:
        print(f"  {entry['explanation']}")

    print(f"\n{'-' * 70}\n")
    print(audit_log.summary())

    audit_log.to_json("audit/decisions_sample.json")
    print(f"\nWrote {len(audit_log.entries)} decisions -> audit/decisions_sample.json")