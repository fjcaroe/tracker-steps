"""Bridge the approved OS-only archive directly from QA read-only to the local WSL runtime."""
import argparse
from pathlib import Path
import subprocess


def transfer(host, distro, stage):
    source = Path(__file__).with_name("pack_focal_print_userspace.py").resolve()
    receiver = source.with_name("receive_focal_print_userspace.py")
    wsl_path = "/mnt/" + receiver.drive[0].lower() + receiver.as_posix()[2:]
    with source.open("rb") as script, subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", host, "/usr/bin/python3.10 - " + stage],
        stdin=script, stdout=subprocess.PIPE,
    ) as producer:
        target = subprocess.run(["wsl", "-d", distro, "-u", "root", "--", "python3", wsl_path, stage],
                                stdin=producer.stdout)
        producer.stdout.close()
        if target.returncode or producer.wait():
            raise SystemExit("System runtime transport failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("pg", "odoo", "extras", "print"))
    parser.add_argument("--qa-host", required=True)
    parser.add_argument("--distro", default="Ubuntu")
    args = parser.parse_args()
    transfer(args.qa_host, args.distro, args.stage)
