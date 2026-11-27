"""Describe which fields and records differ without exposing payslip amounts or worker data."""

from collections import defaultdict


AMOUNT_COLUMNS = ("amount", "quantity", "rate", "total")


def analyze(cr, original, draft, stored, current):
    cr.execute("""SELECT salary_rule_id,code,sequence FROM hr_payslip_line WHERE slip_id IN (%s,%s)
                  GROUP BY salary_rule_id,code,sequence""", [original.id, draft.id])
    sequences = defaultdict(set)
    for rule, code, sequence in cr.fetchall():
        sequences[(rule, code)].add(sequence)
    previous, calculated = defaultdict(list), defaultdict(list)
    for rule, code, *values in stored:
        previous[(rule, code)].append(values)
    for rule, code, *values in current:
        calculated[(rule, code)].append(values)
    changed = []
    for key in sorted(previous.keys() | calculated.keys()):
        old, new = previous[key], calculated[key]
        if old == new:
            continue
        seq = sequences[key]
        if len(seq) != 1 or None in seq:
            raise ValueError("A changed salary rule has ambiguous stored sequence")
        if len(old) != len(new):
            fields = []
        else:
            fields = [name for i, name in enumerate(AMOUNT_COLUMNS) if
                      [row[i] for row in old] != [row[i] for row in new]]
        changed.append({"rule": key[0], "code": key[1], "sequence": seq.pop(), "old_rows": len(old),
                        "new_rows": len(new), "fields": fields})
    changed.sort(key=lambda item: (item["sequence"], item["rule"], item["code"]))
    if not changed:
        raise ValueError("The selected salary slip has no historical difference")
    return changed
