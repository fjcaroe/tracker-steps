"""Compare the staged SyS payroll cohort to the original source projections."""
import argparse
from contextlib import closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
from xml.etree import ElementTree

import psycopg2

from admit_sys_payroll_storage import related_identity
from preflight_original_history_storage import require
from restore_sys_previred_pair import LOCK, SOCKET
from sys_previred_preservation import capture, differences, projection_query


def original_prefix(cr, original, table, field, maximum):
    query = projection_query(table, original['columns'][table])
    source = 'FROM public."' + table + '") original'
    require(query.count(source) == 1, 'sys-cohort-projection-contract')
    cr.execute(query.replace(source, source.replace(') original', ' WHERE "' + field + '"<=%s) original')), (maximum,))
    return cr.fetchone()[0]


def verify_added_employee_rules(cr, filename, original, snapshot, protected):
    body = filename.read_bytes().replace(b'\r\n', b'\n')
    require(hashlib.sha256(body).hexdigest() == '9ba0d55473ba0c108c11c07e90396f72deab72e463ea588b5721527517d2a0b1',
            'sys-cohort-unreviewed-employee-policy')
    cutoff = protected['max_id']
    require(protected['rows'] == original['projections']['ir_rule']['rows'], 'sys-cohort-original-rule-cutoff')

    def xml_id(ref, model):
        module, name = ref.split('.', 1)
        cr.execute('SELECT res_id FROM ir_model_data WHERE module=%s AND name=%s AND model=%s', (module, name, model))
        row, = cr.fetchall()
        return row[0]

    expected = {}
    groups = set()
    for node in ElementTree.fromstring(body).findall('./data/record'):
        fields = {f.get('name'): f for f in node.findall('field')}
        rule_id = xml_id('step_simpledigital_oca_security.' + node.get('id'), 'ir.rule')
        require(rule_id > cutoff and rule_id not in expected, 'sys-cohort-new-rule-overlaps-original')
        expected[rule_id] = (xml_id(fields['model_id'].get('ref'), 'ir.model'), fields['domain_force'].text.strip(),
                             True, True, True, True, True)
        if 'groups' in fields:
            group = re.fullmatch(r"\[\(4,ref\('([\w.]+)'\)\)\]", fields['groups'].get('eval'))
            require(group is not None, 'sys-cohort-rule-group-contract')
            groups.add((rule_id, xml_id(group[1], 'res.groups')))
    cr.execute('SELECT id,model_id,trim(domain_force),active,perm_read,perm_write,perm_create,perm_unlink '
               'FROM ir_rule WHERE id>%s', (cutoff,))
    require(len(expected) == 16 and expected == {k:tuple(v) for k,*v in cr.fetchall()}, 'sys-cohort-unexpected-new-rule')
    cr.execute('SELECT rule_group_id,group_id FROM rule_group_rel WHERE rule_group_id>%s', (cutoff,))
    require(len(groups) == 12 and set(cr.fetchall()) == groups, 'sys-cohort-unexpected-rule-membership')
    for table, key in [('ir_rule','id'), ('rule_group_rel','rule_group_id')]:
        snapshot['projections'][table] = original_prefix(cr, original, table, key, cutoff)
    return {'added_rules':len(expected), 'added_rule_group_links':len(groups)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--employee-policy', type=Path, help='Exact installed Steps XML to verify each new rule and group link')
    args = p.parse_args()
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', args.database),
            'sys-cohort-private-postflight-required')
    baseline = json.loads(args.baseline.read_bytes())
    plan = json.loads(args.plan.read_bytes())
    require(baseline['stage'] == 'reference-restored' and baseline['preserved'] is True
            and plan['database'] == args.database, 'sys-cohort-postflight-identity')
    original = baseline['snapshot']
    # A source field may be adopted by its real module before freezing
    # ir.model.fields. Protect aliases introduced by that installation in the
    # guard and compare the original prefix to the sealed native reference.
    protected = plan['protected']['ir_model_data']
    xml_guard = plan.get('pre_adoption_xml', protected)
    require(xml_guard['max_id'] <= protected['max_id'] and xml_guard['rows'] <= protected['rows'],
            'sys-cohort-invalid-pre-adoption-xml-prefix')
    require(xml_guard['rows'] == original['projections']['ir_model_data']['rows']
            and type(xml_guard['max_id']) is int, 'sys-cohort-original-xml-cutoff')
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with closing(psycopg2.connect(dbname=args.database, host=SOCKET, user='postgres')) as conn:
            conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
            with conn.cursor() as cr:
                snapshot = capture(cr, args.database, original)
                # Extra module-registration aliases are legitimate only above
                # the allocator's old maximum. Compare each original SQL row.
                original_xml = original_prefix(cr, original, 'ir_model_data', 'id', xml_guard['max_id'])
                added_xml_ids = snapshot['projections']['ir_model_data']['rows'] - original_xml['rows']
                snapshot['projections']['ir_model_data'] = original_xml
                employee = (verify_added_employee_rules(cr, args.employee_policy, original, snapshot,
                            plan['protected']['ir_rule']) if args.employee_policy else {})
                drift = differences(original, snapshot)
                ids = related_identity(cr)
                cr.execute("SELECT name,state FROM ir_module_module WHERE name IN ('payroll','payroll_account',"
                           "'step_payroll_oca_api','step_payroll_oca_sys_history','l10n_cl_simpledigital_payroll') "
                           "ORDER BY name")
                states = dict(cr.fetchall())
        result = dict(database=args.database, original_xml=original_xml, added_xml_ids=added_xml_ids,
                      original_projections=len(original['projections']), original_fks=len(original['foreign_keys']),
                      counters=len(original['counters']), differences=drift, source_related_ids=ids,
                      provider_states=states, preserved=not any(drift.values()), **employee)
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        require(result['preserved'], 'sys-cohort-original-storage-drift')


if __name__ == '__main__':
    main()
