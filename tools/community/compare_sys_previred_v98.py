"""Compare October SyS Previred v98 receipts without opening employee data."""
import argparse
import json
from pathlib import Path
import re


PREFIX = "STEPS_SYS_PREVIRED_RECEIPT "
V98_CONTRACT = {
    "period": "2026-10-01",
    "spec": "98",
    "closed_cohort": 5,
    "principal": 5,
    "eligible": 5,
    "dropped": 0,
    "errors": {},
    "fields": 105,
    "rows": 5,
    "annexes": 0,
    "with_positive_afp": 5,
    "compared_stored_afp": True,
}
IDENTITY_FIELDS = ("company_id", "operator_uid")
OUTPUT_FIELDS = ("warnings", "file_sha256")


def read_receipt(path, *, community):
    lines = [line.removeprefix(PREFIX) for line in path.read_text(encoding="utf-8").splitlines()
             if line.startswith(PREFIX)]
    if len(lines) != 1:
        raise ValueError("expected exactly one Previred receipt")
    receipt = json.loads(lines[0])
    enterprise = receipt["enterprise_count"]
    if (receipt["community"] is not community
            or type(enterprise) is not int or enterprise < 0
            or (enterprise == 0) is not community
            or receipt["preserved"] is not True or receipt["rolled_back"] is not True):
        raise ValueError("runtime, preservation or rollback mismatch")
    if community and receipt["october_candidates"] != 1:
        raise ValueError("Community must produce exactly one October cohort")
    proof = receipt["generated"]["98"]
    for key, expected in V98_CONTRACT.items():
        observed = proof[key]
        if type(observed) is not type(expected) or observed != expected:
            raise ValueError(f"v98 contract mismatch: {key}")
    for key in IDENTITY_FIELDS:
        if type(proof[key]) is not int or proof[key] <= 0:
            raise ValueError(f"missing original identity: {key}")
    if proof["operator_uid"] <= 1:
        raise ValueError("expected an original operator")
    if not re.fullmatch(r"[a-f0-9]{64}", proof["file_sha256"]):
        raise ValueError("invalid TXT digest")
    if (type(proof["warnings"]) is not dict
            or any(type(count) is not int or count <= 0 for count in proof["warnings"].values())):
        raise ValueError("invalid warning counts")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--community", action="store_true",
                        help="require a zero-Enterprise Community receipt")
    args = parser.parse_args()
    try:
        reference = read_receipt(args.reference, community=False)
        candidate = read_receipt(args.candidate, community=args.community)
        for key in (*IDENTITY_FIELDS, *OUTPUT_FIELDS):
            if reference[key] != candidate[key]:
                raise ValueError(f"reference mismatch: {key}")
    except (OSError, TypeError, KeyError, ValueError) as exc:
        parser.exit(1, f"Previred comparison failed: {exc}\n")
    print(json.dumps({
        "community": args.community,
        "matches": True,
        "rows": candidate["rows"],
        "fields": candidate["fields"],
        "compared_stored_afp": True,
        "file_sha256": candidate["file_sha256"],
    }))


if __name__ == "__main__":
    main()
