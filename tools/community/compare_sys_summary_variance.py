"""Classify historical SyS BASIC, GROSS and NET differences after proving identical current calculations."""
import argparse
from collections import Counter
import json
from pathlib import Path

from compare_sys_company_drafts import compare


def classify(native, community, baseline_native, baseline_community):
    companies = compare(baseline_native, baseline_community, accounting=True, require_review_policy=True)
    combined = sum(companies.values(), Counter())
    if (len(companies), combined["selected"], combined["same_calculation"], combined["both_rejected"],
        combined["matches_closed"], combined["matching_lines"]) != (12, 133, 130, 3, 97, 2098):
        raise ValueError("The original full-month payroll comparison did not reproduce")
    for recent, baseline in ((native, baseline_native), (community, baseline_community)):
        expected = {r["source"]: r for r in baseline["samples"] if "draft" in r and not r["equals_stored"]}
        current = {r["source"]: r for r in recent["samples"]}
        if len(expected) != 33 or current.keys() != expected.keys() or len(recent["samples"]) != 33:
            raise ValueError("The new drafts must cover precisely the original 33 differences")
        if recent["uid"] != baseline["uid"] or recent["native"] != baseline["native"]:
            raise ValueError("The operator or engine does not match the original comparison")
        for pk in expected:
            for field in ("company", "period", "source", "draft", "stored", "lines", "equals_stored"):
                if current[pk].get(field) != expected[pk][field]:
                    raise ValueError("A fresh draft differs from its original source or computation fingerprint")
    peer = {r["source"]: r for r in community["samples"]}
    groups = Counter()
    code_totals = Counter()
    for row in native["samples"]:
        if "draft" not in row:
            continue
        flags = row["summary_rules"]
        if flags != peer[row["source"]]["summary_rules"]:
            raise ValueError("The native and Community summary rules differ")
        total_codes = flags["changed_totals"]
        if not set(total_codes) <= set(flags["changed_rows"]):
            raise ValueError("Inconsistent summary classification")
        if row["equals_stored"]:
            if flags["changed_rows"]:
                raise ValueError("An equal historical case reported a different summary")
            continue
        if total_codes:
            groups["summary_totals_changed"] += 1
            code_totals.update(total_codes)
        elif flags["changed_rows"]:
            groups["summary_rows_changed_with_equal_totals"] += 1
        else:
            groups["only_other_rules_changed"] += 1
    if sum(groups.values()) != 33:
        raise ValueError("Unexpected number of historical differences")
    return {"baseline_equal_to_closed": 97, "baseline_rejected_at_contract_review": 3, "baseline_calculated_identically": 130,
            "fresh_drafts_per_engine": 33,
            "historical_differences": 33, "by_impact": {k: groups[k] for k in ("summary_totals_changed",
                "summary_rows_changed_with_equal_totals", "only_other_rules_changed")},
            "individual_total_differences": {code: code_totals[code] for code in ("BASIC", "GROSS", "NET")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("community", type=Path)
    parser.add_argument("baseline_native", type=Path)
    parser.add_argument("baseline_community", type=Path)
    args = parser.parse_args()
    print(json.dumps(classify(*(json.loads(f.read_bytes()) for f in (args.native, args.community,
                          args.baseline_native, args.baseline_community))), sort_keys=True))
