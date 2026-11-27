"""Check authenticated Steps support pages, ticket links and downloaded message files against the native reference."""
import argparse
import json
from pathlib import Path


def compare(original, community, *, target="COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3"):
    assert __debug__
    assert original["db"] == "MANAGEMENT_QA_STEPS_CRM_20261126U42C"
    assert target in ("COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3", "COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A",
                      "COMMUNITY_STEPS_CRM_FISCAL_20261127U45F","COMMUNITY_STEPS_EXPENSE_20261127U50E")
    assert community["db"] == target
    assert original["probe_sha256"] == community["probe_sha256"]
    assert original["unchanged_table_rows"] == community["unchanged_table_rows"] == 15
    reference = original["result"]
    actual = community["result"]
    assert not ("error" in actual or "error" in reference)
    assert reference.keys() == actual.keys()
    for key in reference:
        assert actual[key] == reference[key], key
    assert set(actual["extended_form_parameters"]) == {"steps_stage", "steps_priority", "steps_status", "steps_assignment", "steps_period"}
    assert actual["authenticated_sessions"] == 2
    assert len(actual["visible_order"]) == len(actual["linked_ticket_pages"]) == actual["recipient_details"] == 5
    assert all(item == ["direct", True] for item in actual["linked_ticket_pages"])
    assert actual["other_details_denied"] == actual["anonymous_details_denied"] == 5
    assert len(actual["messages"]) == 3 and len(actual["files"]) == 2
    assert sum(v[0] for v in actual["files"].values()) == 228178
    assert actual["temporary_link_accepted"] and actual["invalid_link_denied"] and actual["expired_link_denied"]
    return {"tickets": 5, "sort_orders": len(actual["sorts"]), "filters": len(actual["filters"]),
            "groups": len(actual["groups"]), "searches": len(actual["search"]),
            "additional_form_parameters": sorted(actual["extended_form_parameters"]),
            "messages": 3, "attachments": 2, "attachment_bytes": 228178, "unchanged_tables_per_copy": 15}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("community", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.native.read_bytes()), json.loads(args.community.read_bytes())), indent=2))
