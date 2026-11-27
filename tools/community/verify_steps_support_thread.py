"""Verify independent ticket chatter and file receipts on the Steps original and Community copies."""
import argparse
import json
from pathlib import Path


def compare(native, community):
    if not __debug__:
        raise ValueError("Run with assertions enabled.")
    assert native["db"] == "MANAGEMENT_QA_STEPS_CRM_20261126U42C"
    assert community["db"] == "COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3"
    assert native["probe_sha256"] == community["probe_sha256"]
    assert native["unchanged_table_rows"] == community["unchanged_table_rows"] == 11
    original = native["result"]
    assert "error" not in original and original == community["result"]
    operators, portal = original["operators"], original["portal"]
    assert len(operators) == 2 and all(c["threads"] == 243 and c["messages"] and c["attachments"] for c in operators)
    assert portal["invited_threads"] == 5 and portal["unrelated_or_public_thread_denials"] == 3
    assert portal["messages"] and portal["attachment_bytes"] and portal["public_attachment_record_denials"] == portal["attachments"]
    return original


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("community", type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.native.read_bytes()), json.loads(args.community.read_bytes())), indent=2))
