"""Compare native ticket page boundaries with the stable responsible-user order in the Steps portal."""
import argparse
import json
from pathlib import Path

from verify_converted_backup import check, hash_file, read_json


NATIVE = "10959117c5353e17a5b02e2f279d7b3d5292d4e1fc9d3430be65ca8e86c37e1d"


def verify(native, community):
    original, updated = read_json(native), read_json(community)
    check(hash_file(native) == NATIVE and original["by_ticket"] == updated["by_ticket"] == [1, 1, 1, 1, 2],
          "unknown-native-responsible-user-partitions")
    cases = {(s["plan"], s["limit"]): s for s in original["steps"]}
    current = {(s["plan"], s["limit"]): s for s in updated["steps"]}
    check(cases.keys() == current.keys() == {(plan, limit) for plan in ("default", "indexes", "scan") for limit in (2, 80)},
          "missing-pagination-cases")
    for (plan, limit), before in cases.items():
        after = current[plan, limit]
        check(before["complete_unique"] and after["complete_unique"] and before["group_runs"] == after["group_runs"] ==
              [1, 1, 1, 1, 2], "ticket-membership-or-responsible-user-priority-drift")
        check(before["order"] == ([3, 4, 2, 1, 5] if limit == 2 else [4, 3, 2, 1, 5]) and
              after["order"] == [4, 3, 2, 1, 5], "unstable-paginated-order")
        check([row[1:3] for row in before["queries"]] == [row[1:3] for row in after["queries"]]
              and all(row[0] == "user_id" for row in before["queries"]) and
              all(row[0] == "user_id, id desc" for row in after["queries"]), "unexpected-sort-expansion")
    return {"native_sha256": NATIVE, "integrated_sha256": hash_file(community), "plans": 3,
            "page_sizes": [2, 80], "responsible_user_groups": 2, "tickets": 5,
            "native_complete_page_order": [4, 3, 2, 1, 5], "native_split_page_order": [3, 4, 2, 1, 5],
            "stable_complete_and_split_page_order": [4, 3, 2, 1, 5]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("community", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.native, args.community), indent=2))
