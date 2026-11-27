"""Verify the final ticket and portal release receipts of the recovered Steps sales and document installation."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from verify_steps_support_portal_http import compare as http_compare
from verify_steps_support_thread import compare as thread_compare


SUPPORT = "step_helpdesk_tickets"
PORTAL = "step_helpdesk_tickets_portal"
PACKAGES = {SUPPORT: ("327c5bc269d9ee64dab3bd49735f350300552466c046a8013566636b3e99adad", 6),
            PORTAL: ("4c70b5c6e9a7ddc1409fd93aece9cca5b028367c5955942ccbc579eebd223dbc", 7)}


def verify(folder):
    assert __debug__
    raw = {name: (folder / (name + ".json")).read_bytes() for name in (
        "native-chatter", "community-chatter", "native-http", "community-http", "native-audit", "community-audit", "upgrade", "repeat")}
    evidence = {name: json.loads(data) for name, data in raw.items()}
    http = http_compare(evidence["native-http"], evidence["community-http"])
    chatter = thread_compare(evidence["native-chatter"], evidence["community-chatter"])
    before, after = evidence["native-audit"], evidence["community-audit"]
    assert (before["db"], after["db"]) == (evidence["native-http"]["db"], evidence["community-http"]["db"])
    assert before["unchanged_table_rows"] == after["unchanged_table_rows"] == 11
    assert before["result"] == after["result"] and before["probe_sha256"] == after["probe_sha256"]
    audit = after["result"]
    assert audit["created_by_operator"] and audit["timestamped_create"] and audit["stage_change_kept_creator"] and audit["timestamped_write"]
    masters = {name: facts["records"] for name, facts in audit["historical"].items()}
    assert masters == {"helpdesk.ticket": 243, "helpdesk.team": 3, "helpdesk.stage": 7, "helpdesk.tag": 22}
    assert all(f["automatic_audit"] and not f["absent"] and f["column_types"] ==
               [["datetime", True], ["datetime", True], ["many2one", True], ["many2one", True]] for f in audit["historical"].values())
    for name, (sha, count) in PACKAGES.items():
        package = folder / (name + ".tar")
        assert hashlib.sha256(package.read_bytes()).hexdigest() == sha
        with tarfile.open(package) as archive:
            members = archive.getmembers()
            assert len(members) == count and len({m.name for m in members}) == count
            assert all(m.isfile() and Path(m.name).parts[0] == name for m in members)
    changed, repeat = evidence["upgrade"], evidence["repeat"]
    for entry in (changed, repeat):
        assert entry["support"] == PACKAGES[SUPPORT][0] and entry["portal"] == PACKAGES[PORTAL][0]
        assert entry["database"] == after["db"] and entry["installed"] == 162
        assert len(entry["loads"]) == 2 and [row["module"] for row in entry["loads"]] == [SUPPORT, PORTAL]
        assert all(row["to"] == "18.0.1.0.2" and row["operation"] == "-u" for row in entry["loads"])
        assert entry["final"]["unchanged_business_tables"] == 313 and entry["final"]["unchanged_original_sql_objects"] == 15183
    assert changed["loads"][0]["from"] == ["18.0.1.0.1", "LGPL-3"] and all(
        row["from"] == ["18.0.1.0.2", "LGPL-3"] for row in repeat["loads"])
    return {"database": after["db"], "source_sql_sha256": repeat["sql"], "installed": 162,
            "ticket_and_portal_sha256": {name: item[0] for name, item in PACKAGES.items()},
            "original_chatter": chatter["operators"][0], "http": http, "audit_records": masters,
            "original_audit_values": 4 * sum(masters.values()), "schema_and_business": repeat["final"],
            "receipts_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in raw.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder), indent=2, sort_keys=True))
