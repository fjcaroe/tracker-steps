"""Read-only comparison of active direct rule configurations and closed SyS payslips."""
from collections import Counter
from contextlib import closing
import json

import psycopg2


REFERENCE = 'l10n_cl_simpledigital_payroll.structure_chile'
DATABASES = ('MANAGEMENT_QA_SYS_PREVIRED_20261126U40N', 'MANAGEMENT_QA_CERRO_CUSTODY_20261126U40Q',
             'COMMUNITY_PAYROLL_API_CERRO_SCOPE_20261126U40J')


def snapshot(database, with_history=False):
    if database not in DATABASES:
        raise ValueError('Use a designated read-only payroll restore.')
    with closing(psycopg2.connect(dbname=database, host='/var/run/postgresql')) as connection:
        connection.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with connection, connection.cursor() as cr:
            cr.execute("""SELECT res_id FROM ir_model_data WHERE module=%s AND name=%s
                          AND model='hr.payroll.structure'""", REFERENCE.split('.'))
            structure, = cr.fetchall()
            cr.execute("""SELECT r.id,r.code,encode(sha256(convert_to(jsonb_build_array(
                    r.sequence,c.code,r.quantity,r.condition_select,r.condition_range,r.condition_range_min,
                    r.condition_range_max,r.condition_python,r.amount_select,r.amount_fix,r.amount_percentage_base,
                    r.amount_percentage,r.amount_python_compute,to_jsonb(r)->'not_computed_in_net',
                    to_jsonb(r)->'split_move_lines')::text,'UTF8')),'hex')
                FROM hr_salary_rule r LEFT JOIN hr_salary_rule_category c ON c.id=r.category_id
                WHERE r.active AND r.struct_id=%s""", structure)
            rules = {ident: (code, signature) for ident, code, signature in cr.fetchall()}
            history = []
            if with_history:
                cr.execute("""SELECT array_agg(DISTINCT l.salary_rule_id)
                        FROM hr_payslip p JOIN hr_payslip_line l ON l.slip_id=p.id
                        WHERE p.struct_id=%s AND p.state IN ('done','paid') GROUP BY p.id""", structure)
                history = [row[0] for row in cr.fetchall()]
    return rules, history


def compare():
    sys_rules, slips = snapshot(DATABASES[0], with_history=True)
    native, _ = snapshot(DATABASES[1])
    community, _ = snapshot(DATABASES[2])
    original_config, candidate = Counter(native.values()), Counter(community.values())
    if original_config != candidate or not slips:
        raise ValueError('Missing history or different Cerro rule configurations.')
    mismatches = [sum(sys_rules.get(ident) not in original_config for ident in used) for used in slips]
    return {'sys_direct_rules': len(sys_rules), 'cerro_direct_rules': len(native),
            'common_direct_signatures': sum((Counter(sys_rules.values()) & original_config).values()),
            'closed_sys_slips_with_lines': len(slips), 'closed_slips_using_only_matched_rules': mismatches.count(0),
            'unmatched_rules_per_slip': [min(mismatches), max(mismatches)]}


if __name__ == '__main__':
    print(json.dumps(compare(), sort_keys=True))
