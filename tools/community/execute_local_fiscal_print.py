"""Execute the guarded official extension install and original report action in isolated WSL."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from restore_local_fiscal_print import WORK


def run(stage):
    runner = Path(__file__).with_name("run_focal_print_command.py")
    out = WORK / "proofs"
    out.mkdir(exist_ok=True, mode=0o700)
    cmds = json.loads((WORK / "commands.json").read_bytes())
    check = stage in ("restored", "installed", "rendered")
    if stage == "install" and not (out / "restored.json").exists():
        raise ValueError("The complete restored source must pass before installing")
    if stage == "pdf" and not (out / "installed.json").exists():
        raise ValueError("The installed source must pass before printing")
    command = [sys.executable, str(runner)]
    if stage == "pdf":
        command.append("--loopback")
    command.extend(["--user", "postgres" if check else "odoo", "--"])
    if stage == "pdf":
        # Check both executable paths before Odoo persists a fallback CSS cache.
        test = subprocess.run([*command, "sassc", "-t", "compressed", "/work/sys-print/code/compiler-probe.scss"], capture_output=True)
        if test.returncode or b"111827" not in test.stdout:
            raise ValueError("The original PDF stylesheet compiler is unavailable")
        subprocess.run([*command, "gs", "-q", "-dNODISPLAY", "-dBATCH", "-c", "quit"], check=True)
    command.extend(["python3.10", "/work/sys-print/code/check_local_fiscal_print.py", stage] if check else cmds[stage])
    data = (WORK / "shell-input.py").read_bytes() if stage == "pdf" else None
    run = subprocess.run(command, input=data, capture_output=True)
    (out / (stage + ".stderr")).write_bytes(run.stderr)
    (out / (stage + ".stdout")).write_bytes(run.stdout)
    if run.returncode:
        raise SystemExit("Private command failed. See " + str(out / (stage + ".stderr")))
    if check:
        result = json.loads(run.stdout)
        print(stage, result["modules"], result["source_rows"], sorted(result["changed_tables"]))
    elif stage == "pdf":
        rows = [line for line in run.stdout.splitlines() if line.startswith(b"SYS_LOCAL_PRINT ")]
        if len(rows) != 1:
            raise ValueError("Missing receipt from the four actual fiscal PDF renders")
        result = json.loads(rows[0].split(b" ", 1)[1])
        print(stage, len(result["printed"]), result["renderer_sha256"])
    else:
        result = {"status": run.returncode}
        print(stage, run.returncode)
    (out / (stage + ".json")).write_text(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("restored", "install", "installed", "pdf", "rendered"))
    os.umask(0o077)
    run(parser.parse_args().stage)
