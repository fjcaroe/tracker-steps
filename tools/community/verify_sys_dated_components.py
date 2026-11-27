"""Test dated credit and salary-rule inputs against complete, preserved October payslip fingerprints."""

import ast
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import fcntl
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

from rehearse_sys_module_upgrades import odoo
from replay_sys_rule_variance import BASE, CODE, DB, PROBES, ROOT
from restore_sys_previred_pair import LOCK, require
from trace_sys_historical_rule_sources import ARCHIVES, collect, credit, digest, fingerprint, numeric, read_dump, same_formula


FORMULAS = {25:"5990fa4374261d11810b2e76aff3a519fc265c7a0f4badcbad17cc4405309fec",
    35:"633290fc7ac9446a73b2f594f42cae55bb9288d6c93f482fe2f8fffc328f3bc6",36:"bd4b9fdf0fa16f128533967f2f762a7c806d40d72954e4bb340c2e408c3497c5",
    41:"a65daec122bc252b2fcd854b6408825f11f6e897c6c144249993f9bce953b8d8",51:"8ec1b072d1554b561a01b2e1dd0fd5c93b47b67551e4a44e78e13063b905f055",
    60:"e29f407430ee205d08561eedb5ae230dc592c7771cc0a6f0831d484e29c895aa",77:"aeedb4377cd1c691d9c7684046978262c8a72062cc0207b7a607c8fe8383d803"}
DEDUCTIONS = ("AFP","SALUD","EXD","AFC_T","APVI","APVC_T","APV_EMP","CUENTA2","RETENCION",
              "CCAF_CREDITO","CCAF_DENTAL","CCAF_SEG_VIDA","CCAF_AHORRO","CCAF_OTROS","others")
AFP = {"33 - 31":"capital", "03 - 13":"cuprum", "05 - 14":"habitat", "29 - 11":"planvital",
       "08 - 6":"provida", "34 - 103":"modelo", "35 - 19":"uno"}


def category_totals(case, sequence):
    totals = defaultdict(Decimal)
    for key, line in case["paid"].items():
        rule = case["rules"][key]
        if int(rule["sequence"]) >= sequence:
            continue
        category = int(rule["category_id"])
        seen = set()
        while category:
            require(category not in seen,"cyclic-payroll-category")
            seen.add(category)
            code, parent = case["categories"][category]
            totals[code] += Decimal(line[-1] or "0")
            category = int(parent) if parent else None
    return totals


def calculate(rule, case):
    c, ps, work = case["contract"],case["ps"],case["work"]
    paid = sum((Decimal(x[2]) for x in work if x[1] in ("WORK100","LEAVECL120")), Decimal(0))
    if rule == 25:
        value = Decimal(c["wage"] or "0") * paid / 30
    elif rule in (35,36):
        option,field = ("payroll_whole_days_meal","colocation") if rule == 35 else ("payroll_whole_days_transport","movility")
        start = max(date.fromisoformat(ps["date_from"]),date.fromisoformat(c["date_start"]))
        end = min(date.fromisoformat(ps["date_to"]),date.fromisoformat(c["date_end"] or ps["date_to"]))
        if case["company"].get(option) == "t":
            paid = paid.quantize(Decimal(".00000001"),rounding=ROUND_HALF_UP).to_integral_value(rounding=ROUND_CEILING)
        days = max(0,min(30,paid,(end-start).days+1))
        value = Decimal(c[field] or "0") * days / 30
    elif rule == 41:
        indicator = case["indicators"][rule]
        rate = Decimal(indicator[AFP[c["afp_option"]]+"_tasa_dependiente"] or "0")
        totals = category_totals(case, int(case["rules"][rule]["sequence"]))
        value = min(totals["GROSS"], Decimal(indicator["tope_afiliados_afp"])) * rate / 100
    elif rule == 77:
        indicator = case["indicators"][rule]
        n = sum(Decimal(c[f] or "0") * n for f,n in (("family_invalid_loads_count",2),
                ("family_maternal_loads_count",1),("family_simple_loads_count",1)))
        value = Decimal(indicator["tramo_"+(c["family_loads_segment"] or "a").lower()] or "0") * n
        absent = sum((Decimal(x[2]) for x in work if x[1] in ("LEAVE90","OUT")), Decimal(0))
        days = min(30,paid)
        if days < 30:
            days += 30 - (paid + absent)
        if days < 25:
            value *= days / 30
    elif rule == 60:
        totals = category_totals(case, int(case["rules"][rule]["sequence"]))
        value = Decimal(round(sum(totals[k] for k in DEDUCTIONS)))
    else:
        raise ValueError("unexpected first rule")
    return numeric(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def preserved_formula(old, now, rule):
    if same_formula(old,now):
        return True
    if rule not in (35,36):
        return False
    before, after = (ast.parse(r["amount_python_compute"]) for r in (old,now))
    if len(after.body) != 1 or not isinstance(after.body[0],ast.If):
        return False
    remainder = ast.Module(body=after.body[0].orelse,type_ignores=[])
    return (ast.dump(before)==ast.dump(remainder) and old["condition_python"]==now["condition_python"] and
            old["category_id"]==now["category_id"])


def reconstruct_credit(case, sample):
    before = [list(line) for _,line in sorted(case["paid"].items())]
    require(fingerprint(before) == sample["stored"],"not-the-original-complete-lines")
    value = Decimal(case["paid"][51][-1])
    current = []
    for line in before:
        if line[0] == 51:
            continue
        if line[0] in (32,60):
            change = value if line[0]==32 else -value
            for index in (2,5):
                line[index] = numeric(Decimal(line[index])+change)
        current.append(line)
    return fingerprint(current)==sample["draft"]


def prepare(sources,selected,current):
    expected, facts = {},{}
    for pk, sample in selected.items():
        present=current[pk]
        history = [(stamp,rows[pk]) for stamp,rows in sources.items() if pk in rows and rows[pk]["closed_match"]]
        require(history,"missing-closed-archive")
        stamp,closed=history[0]
        rule=sample["changes_by_rule"][0]["rule"]
        text=present["rules"][rule]["amount_python_compute"]
        import hashlib
        require(hashlib.sha256(text.encode()).hexdigest()==FORMULAS[rule], "untested-source-formula")
        evidence={"first_rule":rule,"first_exact_closed_archive":stamp,
                  "paid_edited":closed["ps"]["edited"]=="t","same_days":closed["work"]==present["work"]}
        if any(row["rule"]==51 for row in sample["changes_by_rule"]):
            old_credits = credit(closed)
            evidence["credit_source"] = (len(old_credits)==1 and not credit(present) and
                all(k in present["overlap"] and present["overlap"][k]["active"]=="f" and
                    present["overlap"][k]["installment_amount"]==r["installment_amount"]
                    for k,r in old_credits.items()) and sum(Decimal(r["installment_amount"]) for r in old_credits.values())
                == Decimal(present["paid"][51][-1]))
        if rule == 51:
            evidence["whole_draft_reconstructed_by_removing_credit"] = reconstruct_credit(present,sample)
        else:
            evidence["historical_formula_preserved"] = preserved_formula(closed["rules"][rule],present["rules"][rule],rule)
            expected[pk] = [rule,calculate(rule,closed),calculate(rule,present)]
            evidence["same_predicted_total_from_both_snapshots"] = expected[pk][1]==expected[pk][2]
        facts[pk]=evidence
    return expected,facts


def run_drafts(expected,selected):
    folder=ROOT/"dated-probes"
    folder.mkdir(exist_ok=True)
    folder.chmod(0o755)
    for name in PROBES:
        source=CODE/(name+".py")
        target=folder/source.name
        if not target.exists():
            shutil.copyfile(source,target)
            target.chmod(0o644)
        require(digest(source)==digest(target),"dated-probe-drift")
    script=f"""import sys,json
from decimal import Decimal
sys.path.insert(0,{str(folder)!r})
from probe_sys_company_drafts import probe
from probe_sys_payroll_exports_all import snapshot
assert env.cr.dbname=={DB!r}
values={expected!r}
def test_first(original,draft,stored,current):
    rule,old,new=values[original.id]
    before,=[Decimal(r[-1]) for r in stored if r[0]==rule]
    after,=[Decimal(r[-1]) for r in current if r[0]==rule]
    env.cr.execute('SELECT edited FROM hr_payslip WHERE id=%s',[draft.id])
    return {{'paid_equals_predicted_at_close':before==Decimal(old),'draft_equals_predicted_at_close':after==Decimal(old),
             'draft_equals_predicted_today':after==Decimal(new),'fresh_draft_edited':bool(env.cr.fetchone()[0])}}
rows_before=snapshot(env)
result=probe(env,2,selected=set(values),summary=True,components=True,compare_source=test_first)
assert rows_before==snapshot(env)
print('DATED='+json.dumps(result),flush=True)
"""
    args=SimpleNamespace(database=DB,output=ROOT,sealed=BASE)
    log=ROOT/("dated-first-"+str(len(list(ROOT.glob("dated-first-*.log"))))+".log")
    status=odoo(args,"shell",[],log,script.encode())
    lines=[json.loads(l.partition("=")[2]) for l in log.read_text().splitlines() if l.startswith("DATED=")]
    require(not status and len(lines)==1,"dated-draft-replay-failed")
    result={}
    for row in lines[0]["samples"]:
        pk=row["source"]
        require(all(row.get(k)==selected[pk][k] for k in ("draft","stored","changes_by_rule","summary_rules")),
                "dated-scenario-did-not-reproduce-both-original-fingerprints")
        result[pk]=row["dated_value_check"]
    require(result.keys()==expected.keys(),"incomplete-dated-value-checks")
    return result


def main():
    os.umask(0o077)
    selected={r["source"]:r for r in json.loads((ROOT/"community.json").read_bytes())["samples"]}
    sources={}
    for date_tag in ARCHIVES:
        pref="retained_sys_" if date_tag.startswith("20261109") else "management_sys_"
        file=Path("/opt/steps_backups")/(pref+date_tag)/"database.dump"
        if file.is_file():
            sources[date_tag]=collect(read_dump(file),selected)
    current_dump=BASE/"source.dump"
    require(digest(current_dump)=="0c4e970e29579c6de38d71397a987682e97ff9a90027baad8c9e9b77f84bf606","original-L-snapshot-required")
    current=collect(read_dump(current_dump, sealed_source="COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L"),selected)
    expected,facts=prepare(sources,selected,current)
    target=ROOT/"dated-first-components.json"
    if target.is_file():
        raise ValueError("The completed dated test must be reviewed before starting another")
    with open(LOCK,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        observed=run_drafts(expected,selected)
        for pk,values in observed.items():
            facts[pk].update(values)
        with target.open("x") as file:
            json.dump(facts,file,sort_keys=True,indent=2)
        print("cases",len(facts),"additional-private-drafts",len(observed),"receipt",digest(target),flush=True)


if __name__=="__main__":
    main()
