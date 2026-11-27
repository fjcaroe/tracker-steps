"""Run one QA command under the shared Focal userspace in private WSL mount and network namespaces."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/var/tmp/steps-community-qa-focal")
UIDS = {"postgres": 61012, "odoo": 61018, "root": 0}


def run(args):
    if os.getuid() or not (ROOT / "pg-source-members.json").is_file():
        raise ValueError("The verified local PostgreSQL userspace is required")
    if not args.inside:
        os.execvp("unshare", ["unshare", "--mount", "--net", sys.executable, str(Path(__file__).resolve()),
                              "--inside", *sys.argv[1:]])
    subprocess.run(["mount", "--make-rprivate", "/"], check=True)
    subprocess.run(["mount", "-t", "proc", "proc", str(ROOT / "proc")], check=True)
    dev = ROOT / "dev"
    subprocess.run(["mount", "-t", "tmpfs", "-o", "size=8m,mode=755", "tmpfs", str(dev)], check=True)
    for name in ("null", "zero", "random", "urandom"):
        (dev / name).touch()
        subprocess.run(["mount", "--bind", "/dev/" + name, str(dev / name)], check=True)
    (dev / "shm").mkdir(mode=0o1777)
    subprocess.run(["mount", "--bind", "/dev/shm", str(dev / "shm")], check=True)
    if args.steps_expense_recovery:
        source = Path("/tmp/steps-expense-recovery-u50")
        target = dev / "shm/steps-expense-recovery-u50"
        fs = subprocess.check_output(["findmnt", "-n", "-o", "FSTYPE", "--target", str(source)], text=True).strip()
        if fs != "tmpfs" or source.resolve(strict=True) != source or source.stat().st_uid:
            raise ValueError("Expected the private Steps memory volume")
        target.mkdir(mode=0o711, exist_ok=True)
        if target.resolve(strict=True) != target or target.stat().st_uid:
            raise ValueError("Unexpected Steps recovery mount")
        subprocess.run(["mount", "--bind", str(source), str(target)], check=True)
    (dev / "fd").symlink_to("/proc/self/fd")
    if args.sys_payslip_form:
        trials = {"COMMUNITY_SYS_PREVIRED_COHORT_20261127U48C": "sys-u48-payslip",
                  "COMMUNITY_SYS_PREVIRED_COHORT_20261127U48D": "sys-u48-payslip-final",
                  "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49D": "sys-negative-net-u49d",
                  "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49E": "sys-negative-net-u49e",
                  "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49F": "sys-negative-net-u49f",
                  "COMMUNITY_SYS_FINAL_PRINT_RECOVERY_20261127U51S": "sys-negative-net-u49e"}
        db, = (name for name in trials if name in args.command)
        module = "step_payroll_oca_sys_history"
        private = Path("/dev/shm") / trials[db] / "overlay" / module
        target = ROOT / "work/sys-fg-code/addons" / module
        if (args.user != "odoo" or db not in args.command or "--db-filter=^" + db + "$" not in args.command
                or private.resolve() != private or target.resolve() != target or not (private / "payslip_form.py").is_file()):
            raise ValueError("Expected only the isolated SyS form trial")
        if db == "COMMUNITY_SYS_FINAL_PRINT_RECOVERY_20261127U51S" and not args.steps_expense_recovery:
            raise ValueError("Expected the private recovery mount")
        subprocess.run(["mount", "--bind", str(private), str(target)], check=True)
        subprocess.run(["mount", "-o", "remount,bind,ro", str(target)], check=True)
    if args.loopback:
        subprocess.run(["ip", "link", "set", "lo", "up"], check=True)
    uid = UIDS[args.user]
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("Missing command")
    env = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PATH": "/usr/local/bin:/usr/lib/postgresql/12/bin:/usr/bin:/bin",
           "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "USER": args.user}
    launcher = next(str(p) for p in (Path("/usr/bin/chroot"), Path("/usr/sbin/chroot")) if p.is_file())
    os.execve(launcher, [launcher, "--userspec=%d:%d" % (uid, uid), str(ROOT), *command], env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--sys-payslip-form", action="store_true")
    parser.add_argument("--steps-expense-recovery", action="store_true")
    parser.add_argument("--loopback", action="store_true")
    parser.add_argument("--user", choices=UIDS, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    run(parser.parse_args())
