"""Prepare an offline palette install, the original two-operator invoice action and the evidence files on WSL."""
import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import io

from package_steps_print_colors import build
from restore_local_fiscal_print import DB, WORK


def prepare(custody):
    code = WORK / "code"
    code.mkdir(exist_ok=True)
    tools = Path(__file__).resolve().parent
    project = tools.parents[1]
    todo = {"audit_local_print_rows", "check_local_fiscal_print", "original_report_loopback", "load_steps_sales_extension", "probe_sys_invoice_pdf"}
    copied = set()
    while todo:
        name = todo.pop()
        if name in copied:
            continue
        src = tools / (name + ".py")
        shutil.copyfile(src, code / src.name)
        copied.add(name)
        for node in ast.walk(ast.parse(src.read_bytes())):
            if isinstance(node, ast.ImportFrom) and node.module and (tools / (node.module + ".py")).is_file():
                todo.add(node.module)
    frozen = json.loads(gzip.decompress((custody / "source-snapshot.json.gz").read_bytes()))
    mandatory = {name: value[0] for name, value in frozen["columns"].items() if value[1]}
    (code / "compiler-probe.scss").write_text("div { color: #111827; }")
    (code / "required-columns.json").write_bytes(json.dumps(mandatory, sort_keys=True).encode())
    for file in ("source-snapshot.json.gz", "effective-providers.json", "final-schema.json"):
        shutil.copyfile(custody / file, WORK / file)
    package = build(project)
    (WORK / "colors.tar").write_bytes(package)
    with tarfile.open(fileobj=io.BytesIO(package)) as archive:
        for member in archive:
            dest = WORK / "overlay" / member.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.extractfile(member).read())
    # PostgreSQL needs only read access to sealed evidence and scripts.
    os.chown(WORK, 0, 0)
    WORK.chmod(0o755)
    config = WORK / "odoo.conf"
    config.write_text("[options]\ndb_host = /run/sys-55441\ndb_port = 55441\ndb_user = odoo\nlist_db = False\n"
                      "data_dir = /work/sys-print/data\nlog_level = warn\n")
    options = ["-c", "/work/sys-print/odoo.conf", "-d", DB, "--db-filter=^" + DB + "$",
               "--addons-path=/work/sys-print/overlay,/work/sys-fg-code/addons,/work/sys-fg-code/odoo/addons",
               "--data-dir=/work/sys-print/data", "--load=base,web", "--workers=0", "--max-cron-threads=0",
               "--no-http", "--stop-after-init", "--without-demo=all"]
    real = "/work/sys-fg-code/odoo-bin"
    base = "/work/sys-print/code/"
    (WORK / "commands.json").write_text(json.dumps({
        "install": ["python3.10", base + "load_steps_sales_extension.py", real, base + "required-columns.json",
                    hashlib.sha256((code / "required-columns.json").read_bytes()).hexdigest(), *options, "-i", "step_report_print_colors"],
        "pdf": ["python3.10", base + "original_report_loopback.py", "--service-process", "python3.10", real, "shell", *options],
    }))
    (WORK / "shell-input.py").write_text("import sys,json\nsys.path.insert(0,'/work/sys-print/code')\n"
        "from probe_sys_invoice_pdf import run\nprint('SYS_LOCAL_PRINT '+json.dumps(run(env)), flush=True)\n")
    print(json.dumps({"tools": len(copied), "package_sha256": hashlib.sha256(package).hexdigest(),
                      "protected_original_required_columns": len(mandatory)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("custody", type=Path)
    prepare(parser.parse_args().custody)
