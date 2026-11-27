"""Compare October payroll inputs with dated original SyS archives in memory. Write only equality tests and counts."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from custody_sys_previred_filestore import digest
from replay_sys_rule_variance import ROOT
from restore_sys_previred_pair import LOCK, require


ARCHIVES = ("20261029T182017Z", "20261030T012813Z", "20261031T202529Z", "20261103T211520Z",
            "20261106T174530Z", "20261106T180309Z", "20261109T144819Z", "20261113T164522Z", "20261113T175609Z")
TABLES = ("hr_payslip", "hr_payslip_line", "hr_payslip_worked_days", "hr_work_entry_type", "hr_contract",
          "res_company", "previred_indicator", "hr_ccaf_deduction", "hr_salary_rule", "hr_salary_rule_category")
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}
RULE_FIELDS = {25: ("wage",), 35: ("colocation", "date_start", "date_end"), 36: ("movility", "date_start", "date_end"),
               41: ("afp_option", "pension_option"), 77: ("has_family_loads", "family_loads_segment",
                    "family_invalid_loads_count", "family_simple_loads_count", "family_maternal_loads_count")}


def read_dump(path, db=None, sealed_source="SyS"):
    if db:
        require(db == "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44VA", "only-disposable-current-snapshot")
        cmd = ["sudo", "-n", "-u", "postgres", "pg_dump", "--data-only", "--no-owner", "--dbname=" + db]
        for table in TABLES:
            cmd += ["--table", "public." + table]
    else:
        toc = subprocess.check_output(["pg_restore", "--list", str(path)], text=True)
        require(sealed_source in ("SyS", "COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L") and re.search(r"^;\s+dbname: " + re.escape(sealed_source) + "$", toc, re.M), "original-SyS-archive-required")
        cmd = ["pg_restore", "--data-only", "--file=-"]
        for table in TABLES:
            cmd += ["--table", table]
        cmd.append(str(path))
    raw = subprocess.check_output(cmd).decode()
    tables = {}
    target = None
    for line in raw.split("\n"):
        if target is None:
            match = re.fullmatch(r"COPY public\.([a-z_]+) \((.*?)\) FROM stdin;", line)
            if match:
                target, columns = match[1], match[2].split(", ")
                require(target in TABLES and target not in tables and columns[0] == "id", "unexpected-table-projection")
                tables[target] = {}
        elif line == "\\.":
            target = None
        else:
            values = line.split("\t")
            require(len(values) == len(columns), "unexpected-copy-column-count")
            row = {k: (None if val == r"\N" else re.sub(r"\\(.)", lambda m: ESCAPES.get(m[1],m[1]), val))
                   for k, val in zip(columns, values)}
            tables[target][int(row["id"])] = row
    require(target is None and set(tables) == set(TABLES), "incomplete-original-archive")
    return tables


def numeric(value):
    return None if value is None else format(Decimal(value).normalize(), "f")


def group(table, key):
    rows = defaultdict(list)
    for line in table.values():
        if line[key]:
            rows[int(line[key])].append(line)
    return rows


def salary_rows(rows):
    return [[int(l["salary_rule_id"]), l["code"], *(numeric(l[k]) for k in ("amount","quantity","rate","total"))]
            for l in sorted(rows, key=lambda l: (int(l["salary_rule_id"]),int(l["id"])))]


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def collect(t, selected):
    lines = group(t["hr_payslip_line"], "slip_id")
    days = group(t["hr_payslip_worked_days"], "payslip_id")
    loans = group(t["hr_ccaf_deduction"], "employee_id")
    results = {}
    for pk, sample in selected.items():
        ps = t["hr_payslip"].get(pk)
        if not ps:
            continue
        contract = t["hr_contract"][int(ps["contract_id"])]
        company = t["res_company"][int(ps["company_id"])]
        paid = {r[0]: r for r in salary_rows(lines[pk])}
        period = [ps["date_from"], ps["date_to"]]
        overlap = {int(c["id"]): c for c in loans[int(ps["employee_id"])] if c["deduction_type"] == "credit"
                   and c["start_date"] and c["start_date"] <= period[1] and (not c["end_date"] or c["end_date"] >= period[0])}
        work = sorted((int(r["work_entry_type_id"]), t["hr_work_entry_type"][int(r["work_entry_type_id"])]["code"],
                       numeric(r["number_of_days"]), numeric(r["number_of_hours"])) for r in days[pk])
        date_month = lambda r: r["date"] and r["date"][:7] == period[0][:7]
        first = lambda r: r["date"] and r["date"] <= period[0]
        indicators = {}
        for rule, test in ((41,date_month), (77,first)):
            available = [r for r in t["previred_indicator"].values() if test(r)]
            indicators[rule] = max(available, key=lambda r: r["date"]) if available else None
        rules = {i: {k:t["hr_salary_rule"][i].get(k) for k in ("amount_python_compute","condition_python","category_id",
                   "amount_select","condition_select","sequence","write_date")} for i in paid.keys() | {c["rule"] for c in sample["changes_by_rule"]}}
        results[pk] = {"closed_match": ps["state"] in ("paid","done") and fingerprint(salary_rows(lines[pk])) == sample["stored"],
                       "contract": contract, "ps": ps, "overlap": overlap, "company": company, "work": work, "indicators": indicators,
                       "paid": paid, "rules": rules, "categories": {int(r["id"]): (r["code"],r["parent_id"])
                                                                  for r in t["hr_salary_rule_category"].values()}}
    return results


def credit(case):
    rows = case["overlap"]
    return {i: r for i,r in rows.items() if r["active"] == "t"}


def same_formula(a,b):
    return {k:v for k,v in a.items() if k != "write_date"} == {k:v for k,v in b.items() if k != "write_date"}


def explain(selected, history, current):
    cases = []
    for pk, sample in selected.items():
        cur = current[pk]
        matches = [stamp for stamp,rows in history.items() if pk in rows and rows[pk]["closed_match"]]
        row = {"source": pk, "first": sample["changes_by_rule"][0]["rule"], "matching_closed_backups": matches,
               "edited_flag": cur["ps"]["edited"] == "t", "compute_date": cur["ps"]["compute_date"]}
        if not matches:
            cases.append(row)
            continue
        close = history[matches[0]][pk]
        row["same_work_entries"] = cur["work"] == close["work"]
        row["same_original_ids"] = all(cur["ps"][k] == close["ps"][k] for k in ("company_id","employee_id","contract_id","struct_id"))
        row["first_formula_identical"] = same_formula(cur["rules"][row["first"]], close["rules"][row["first"]])
        row["inputs_changed"] = [f for f in RULE_FIELDS.get(row["first"],()) if cur["contract"].get(f) != close["contract"].get(f)]
        if row["first"] in (35,36):
            option = "payroll_whole_days_meal" if row["first"] == 35 else "payroll_whole_days_transport"
            row["old_whole_days_option"] = close["company"].get(option) == "t"
            row["new_whole_days_option"] = cur["company"].get(option) == "t"
        if row["first"] in (41,77):
            rule = row["first"]
            indicators = [m["indicators"][rule] for m in (close,cur)]
            row["indicator_dates"] = [m["date"] if m else None for m in indicators]
            row["indicator_fields_changed"] = sorted(k for k in cur["indicators"][rule] if
                close["indicators"][rule].get(k) != cur["indicators"][rule].get(k))
        if any(c["rule"] == 51 for c in sample["changes_by_rule"]):
            then, now = credit(close), credit(cur)
            total = Decimal(cur["paid"][51][-1])
            original = sum((Decimal(c["installment_amount"] or "0") for c in then.values()),Decimal(0))
            row["credit"] = {"then_active":len(then),"now_active":len(now),"old_sum_equals_paid": original == total,
                "same_rows_now_inactive": bool(then) and all(i in cur["overlap"] and
                    cur["overlap"][i]["active"] == "f" and cur["overlap"][i]["installment_amount"] == c["installment_amount"]
                    for i,c in then.items()),
                "current_last_write_dates": sorted({cur["overlap"][i]["write_date"][:10] for i in then if i in cur["overlap"]}),
                "last_snapshot_matching_active": max((key for key in matches if credit(history[key][pk]).keys() == then.keys()), default=None)}
        cases.append(row)
    return cases


def main():
    require(ROOT.is_dir() and (ROOT / "classification.json").is_file(), "completed-verified-replays-required")
    samples = json.loads((ROOT / "native.json").read_bytes())["samples"]
    require(len(samples)==33 and all("changes_by_rule" in r for r in samples), "original-33-required")
    selected = {r["source"]:r for r in samples}
    os.umask(0o077)
    with open(LOCK,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        sources,history = {},{}
        for stamp in ARCHIVES:
            prefix = "retained_sys_" if stamp.startswith("20261109") else "management_sys_"
            archive = Path("/opt/steps_backups") / (prefix+stamp) / "database.dump"
            if not archive.is_file() and prefix == "retained_sys_":
                continue
            sources[stamp] = digest(archive)
            history[stamp] = collect(read_dump(archive), selected)
        current = collect(read_dump(None, "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44VA"), selected)
        rows = explain(selected, history, current)
        result = {"archives":sources,"cases":rows,"cases_with_matching_closed_archive":sum(bool(r["matching_closed_backups"]) for r in rows)}
        target = ROOT / "dated-sources.json"
        if target.exists():
            require(json.loads(target.read_bytes())==result, "previous-source-audit-differs")
        else:
            with target.open("x") as f:
                json.dump(result,f,sort_keys=True,indent=2)
        print("dates",list(sources),"archived closed cases",result["cases_with_matching_closed_archive"],
              "dated active-to-inactive credits",sum(r.get("credit",{}).get("same_rows_now_inactive",False) for r in rows),
              "receipt",digest(target),flush=True)


if __name__ == "__main__":
    main()
