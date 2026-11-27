"""Verify the native and 165-module Steps support workflow receipts outside the server."""
import argparse
import json
from pathlib import Path

from verify_converted_backup import check, hash_file, read_json
from verify_steps_support_backup import ACCEPTANCE, SOURCE, SUCCESSOR
from verify_steps_support_portal_http import compare


REFERENCE = "9851776eb44ad2734a251cad40861aab9909d4aead78665b543cfe7ead736646"


def verify(folder):
    native = folder / "U46A-165-reference.json"
    candidate = folder / "U46A-165-candidate.json"
    original, actual = read_json(native), read_json(candidate)
    accepted = read_json(folder / "acceptance.json")
    check(__debug__ and hash_file(folder / "acceptance.json") == actual["H3_acceptance_sha256"] ==
          original["H3_acceptance_sha256"] == ACCEPTANCE and actual["H3"] == original["H3"] == SOURCE,
          "unrecognized-H3-functional-acceptance")
    check(hash_file(native) == actual["reference_sha256"] == REFERENCE and actual["db"] == SUCCESSOR and
          actual["modules"] == 165, "unrecognized-native-proof-or-integrated-product")
    web = compare(original["http"], actual["http"], target=SUCCESSOR)
    check(web == actual["verified_http"] == accepted["http"] and
          original["thread"] == actual["thread"] and actual["thread"]["operators"] == [accepted["original_chatter"]] * 2,
          "integrated-tickets-or-portals-differ")
    storage = read_json(folder / "checkpoint.json")
    check(actual["unchanged_tables"] >= storage["tables"] and actual["unchanged_sql_objects"] >= storage["schema_objects"]
          and actual["unchanged_physical_files"] > 0, "missing-integrated-storage-comparison")
    portal = actual["thread"]["portal"]
    check(portal["attachments"] == portal["portal_attachment_record_denials"] == portal["public_attachment_record_denials"] == 2
          and portal["attachment_bytes"] == 228178 and portal["unrelated_or_public_thread_denials"] == 3,
          "ordinary-portal-permission-drift")
    return {"database": actual["db"], "checkpoint": hash_file(folder / "checkpoint.json"),
            "providers": actual["modules"], "operators": 2, "tickets": accepted["original_chatter"]["threads"],
            "operator_messages": accepted["original_chatter"]["messages"],
            "operator_attachments": accepted["original_chatter"]["attachments"], "http": web,
            "tables": actual["unchanged_tables"], "sql_objects": actual["unchanged_sql_objects"],
            "physical_files": actual["unchanged_physical_files"], "advanced_sequences": len(actual["forward_sequences"]),
            "reference_sha256": REFERENCE, "candidate_sha256": hash_file(candidate)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
