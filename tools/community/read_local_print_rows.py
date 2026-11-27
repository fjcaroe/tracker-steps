"""Stream selected official COPY records from the off-host custody through private PostgreSQL verification."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from restore_local_fiscal_print import WORK, sha


def compare(dump, stage):
    if sha(dump) != "435bd9ba963688ce202107c1f63351080e55296ff25a4bdc1d23f2f0fb76bf83":
        raise ValueError("Unexpected original FG dump")
    run = [sys.executable, str(Path(__file__).with_name("run_focal_print_command.py")), "--user", "postgres", "--"]
    tables = ("ir_module_module", "ir_module_module_dependency", "ir_model_data", "ir_cron_trigger", "ir_ui_view",
              "ir_attachment")
    filters = [arg for table in tables for arg in ("-t", table)]
    with dump.open("rb") as inp, subprocess.Popen([*run, "pg_restore", "-a", *filters, "-f", "-"], stdin=inp,
                                                  stdout=subprocess.PIPE) as producer:
        result = subprocess.run([*run, "python3.10", "/work/sys-print/code/audit_local_print_rows.py"],
                                stdin=producer.stdout, capture_output=True)
        producer.stdout.close()
        if result.returncode or producer.wait():
            raise ValueError(result.stderr.decode()[-1800:])
    rows = json.loads(result.stdout)
    evidence = WORK / (stage + "-rows.json")
    evidence.write_bytes(result.stdout)
    evidence.chmod(0o644)
    print(json.dumps(rows))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dump", type=Path)
    p.add_argument("stage", choices=("installed", "rendered"))
    args = p.parse_args()
    compare(args.dump, args.stage)
