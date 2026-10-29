"""Read-only batch adoption contract. Never converts, upgrades or loads Odoo.

Only existing private validation copies are accepted. Enterprise implementation
bodies, view architecture, server-action code, bank payloads, names and financial
amounts are not exported. The private artifact keeps metadata and opaque row
fingerprints needed to reject identity/storage loss before a real provider runs.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET


MODEL = 'account.batch.payment'
NATIVE_MODULES = ('account_batch_payment', 'account_accountant_batch_payment')
OWN_MODULES = ('step_account_treasury_batch', 'step_bank_security', 'step_bank_export_core')
PRIVATE_DATABASE = re.compile(r'(?:COMMUNITY_[A-Za-z0-9_]+|MANAGEMENT_QA_(?:CERRO|SYS|STEPS)_[A-Za-z0-9_]+)\Z')
PRIVATE_ROOT = Path('/opt/steps-validation')


def validate_database(name):
    if not PRIVATE_DATABASE.fullmatch(name):
        raise ValueError('Only an existing private validation database is allowed')
    return name


def identifier(name):
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', name):
        raise ValueError('Unexpected SQL identifier')
    return '"' + name + '"'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def view_api(architecture):
    """Only public method/field identifiers and a digest, never OEEL XML bodies."""
    if isinstance(architecture, dict):
        architecture = architecture.get('en_US') or next(iter(architecture.values()), '')
    source = architecture or ''
    result = {'sha256': hashlib.sha256(source.encode()).hexdigest(), 'fields': [], 'object_methods': []}
    if source:
        root = ET.fromstring(source)
        result['fields'] = sorted({node.attrib['name'] for node in root.iter('field') if node.get('name')})
        result['object_methods'] = sorted({node.attrib['name'] for node in root.iter('button')
                                           if node.get('type') == 'object' and node.get('name')})
    return result


def licensed_candidate(root):
    """Inspect an explicitly supplied Community candidate without importing it.

    Manifests/code with an Enterprise license are refused. Only declarations,
    field identifiers, method names and file hashes enter the private contract.
    """
    manifest_path = root / '__manifest__.py'
    manifest = ast.literal_eval(manifest_path.read_text())
    if manifest.get('license') not in ('AGPL-3', 'LGPL-3', 'GPL-3'):
        raise ValueError('Candidate license is not an explicitly declared Community license')
    result = {'module': root.name, 'version': manifest['version'], 'license': manifest['license'],
              'depends': manifest.get('depends', []), 'models': [], 'source_files_sha256': {}}
    for path in sorted(root.rglob('*.py')):
        result['source_files_sha256'][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, ast.ClassDef):
                continue
            info = {'class': node.name, 'fields': [], 'methods': []}
            for member in node.body:
                if isinstance(member, ast.FunctionDef):
                    info['methods'].append(member.name)
                elif isinstance(member, ast.Assign) and isinstance(member.targets[0], ast.Name):
                    key = member.targets[0].id
                    if key in ('_name', '_inherit', '_table'):
                        info[key] = ast.literal_eval(member.value)
                    elif isinstance(member.value, ast.Call) and isinstance(member.value.func, ast.Attribute) and (
                            isinstance(member.value.func.value, ast.Name) and member.value.func.value.id == 'fields'):
                        info['fields'].append(key)
            if any(key in info for key in ('_name', '_inherit')):
                result['models'].append(info)
    return result


def metadata_json(cursor, query, params=()):
    cursor.execute(query, params)
    return cursor.fetchone()[0]


def fingerprints(cursor, tables):
    result = {}
    for table in sorted(set(tables)):
        quoted = identifier(table)
        cursor.execute('SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,E\'\\n\' '
                       'ORDER BY to_jsonb(t)::text),\'\')) FROM ' + quoted + ' t')
        count, row_hash = cursor.fetchone()
        result[table] = {'rows': count, 'stored_rows_md5': row_hash}
    return result


def history_fingerprints(cursor):
    """Retain original file references/checksums and chatter, never their bodies."""
    result = {}
    scopes = {
        'ir_attachment': 't.res_model=%s',
        'mail_message': 't.model=%s',
        'mail_followers': 't.res_model=%s',
        'mail_activity': 't.res_model=%s',
        'mail_tracking_value': 'EXISTS(SELECT 1 FROM mail_message m WHERE m.id=t.mail_message_id AND m.model=%s)',
    }
    for table, where in scopes.items():
        cursor.execute('SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,E\'\\n\' '
                       'ORDER BY to_jsonb(t)::text),\'\')) FROM ' + identifier(table) + ' t WHERE ' + where, (MODEL,))
        count, row_hash = cursor.fetchone()
        result[table + '@' + MODEL] = {'rows': count, 'stored_rows_md5': row_hash}
    return result


def collect(cursor):
    cursor.execute('SHOW transaction_read_only')
    if cursor.fetchone()[0] != 'on':
        raise ValueError('The preflight must run inside a read-only transaction')
    cursor.execute('SHOW transaction_isolation')
    if cursor.fetchone()[0] != 'repeatable read':
        raise ValueError('Use one repeatable-read metadata/history snapshot')
    models = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(m)-'write_date'-'write_uid' ORDER BY m.id),'[]')
        FROM ir_model m WHERE m.model LIKE 'account.batch.%%' OR m.model IN (
            'account.payment','account.payment.method','account.payment.method.line',
            'bank.rec.widget','bank.rec.widget.line','step.cashflow.line','step.cashflow.batch.wizard')""")
    fields = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(f)-'write_date'-'write_uid'-'compute' ORDER BY f.id),'[]')
        FROM ir_model_fields f WHERE f.model LIKE 'account.batch.%%' OR f.relation=%s
        OR f.model='step.cashflow.batch.wizard'
        OR (f.model IN ('account.payment','account.payment.method','account.payment.method.line')
            AND (f.name LIKE '%%batch%%' OR f.name IN ('is_matched','is_reconciled','move_id','outstanding_account_id')))""", (MODEL,))
    field_ids = [row['id'] for row in fields]
    model_ids = [row['id'] for row in models]
    xmlids = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(d)-'write_date'-'write_uid' ORDER BY d.id),'[]')
        FROM ir_model_data d WHERE d.module=ANY(%s)
        OR (d.model='ir.model.fields' AND d.res_id=ANY(%s)) OR (d.model='ir.model' AND d.res_id=ANY(%s))""",
        (list(NATIVE_MODULES + OWN_MODULES), field_ids, model_ids))
    selections = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(s)-'write_date'-'write_uid' ORDER BY s.id),'[]')
        FROM ir_model_fields_selection s WHERE s.field_id=ANY(%s)""", (field_ids,))
    access = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(a)-'write_date'-'write_uid' ORDER BY a.id),'[]')
        FROM ir_model_access a WHERE a.model_id=ANY(%s)""", (model_ids,))
    rules = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(r)-'write_date'-'write_uid' ORDER BY r.id),'[]')
        FROM ir_rule r WHERE r.model_id=ANY(%s)""", (model_ids,))
    rule_ids = [row['id'] for row in rules]
    rule_groups = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.rule_group_id,t.group_id),'[]')
        FROM rule_group_rel t WHERE t.rule_group_id=ANY(%s)""", (rule_ids,))
    owners = metadata_json(cursor, """SELECT coalesce(jsonb_agg(jsonb_build_object('id',m.id,'name',m.name,
        'version',m.latest_version,'state',m.state,'license',m.license) ORDER BY m.name),'[]')
        FROM ir_module_module m WHERE m.name=ANY(%s)""", (list(NATIVE_MODULES + OWN_MODULES) + ['account'],))
    incoming = [row for row in fields if row.get('relation') == MODEL and row['model'] != MODEL]
    tables = ['account_batch_payment', 'account_payment', 'step_cashflow_line',
              'step_cashflow_batch_wizard', 'account_batch_error_wizard', 'bank_rec_widget_line']
    tables += [row['relation_table'] for row in fields if row.get('relation_table')]
    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename=ANY(%s)", (tables,))
    present_tables = [row[0] for row in cursor.fetchall()]
    relation_owners = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY r.id),'[]')
        FROM ir_model_relation r WHERE r.name=ANY(%s)""", (present_tables,))
    columns = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.table_name,c.ordinal_position),'[]')
        FROM (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default
              FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(%s)) c""", (present_tables,))
    constraints = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.table_name,c.name),'[]') FROM (
        SELECT conrelid::regclass::text AS table_name,conname AS name,contype AS type,convalidated AS validated,
            confrelid::regclass::text AS referenced_table,pg_get_constraintdef(oid) AS definition
        FROM pg_constraint WHERE connamespace='public'::regnamespace
        AND (conrelid::regclass::text=ANY(%s) OR confrelid='account_batch_payment'::regclass)) c""",
        (present_tables,)) if 'account_batch_payment' in present_tables else []
    view_rows = metadata_json(cursor, """SELECT coalesce(jsonb_agg(jsonb_build_object('id',v.id,'model',v.model,
        'inherit_id',v.inherit_id,'type',v.type,'active',v.active,'priority',v.priority,'arch',v.arch_db) ORDER BY v.id),'[]')
        FROM ir_ui_view v WHERE v.model LIKE 'account.batch.%%'
        OR v.id IN (SELECT res_id FROM ir_model_data WHERE model='ir.ui.view' AND module=ANY(%s))""",
        (list(NATIVE_MODULES),))
    views = [dict((key, value) for key, value in row.items() if key != 'arch') | {'api': view_api(row['arch'])}
             for row in view_rows]
    actions = metadata_json(cursor, """SELECT coalesce(jsonb_agg(jsonb_build_object('id',a.id,'res_model',a.res_model,
        'view_mode',a.view_mode,'view_id',a.view_id,'target',a.target) ORDER BY a.id),'[]')
        FROM ir_act_window a WHERE a.res_model LIKE 'account.batch.%%'""")
    sequences = metadata_json(cursor, """SELECT coalesce(jsonb_agg(to_jsonb(s)-'write_date'-'write_uid' ORDER BY s.id),'[]')
        FROM ir_sequence s WHERE s.code IN ('account.payment','account.inbound.batch.payment','account.outbound.batch.payment')""")
    sequence_ids = [row['id'] for row in sequences]
    cursor.execute("SELECT sequencename FROM pg_sequences WHERE schemaname='public' AND sequencename ~ '^ir_sequence_[0-9]+(_[0-9]+)?$'")
    counter_names = [row[0] for row in cursor.fetchall() if any(
        re.fullmatch('ir_sequence_%03d(?:_[0-9]+)?' % seq_id, row[0]) for seq_id in sequence_ids)]
    counters = {}
    for name in sorted(counter_names):
        cursor.execute('SELECT last_value,is_called FROM ' + identifier(name))
        last, called = cursor.fetchone()
        counters[name] = {'last_value': last, 'is_called': called}
    profile = {'batch_rows': 0, 'states': [], 'linked_payments': 0, 'export_attachment_rows': 0}
    if 'account_batch_payment' in present_tables:
        cursor.execute('SELECT state,count(*) FROM account_batch_payment GROUP BY state ORDER BY state')
        profile['states'] = [{'state': state, 'rows': count} for state, count in cursor.fetchall()]
        profile['batch_rows'] = sum(row['rows'] for row in profile['states'])
        cursor.execute('SELECT count(*) FROM account_payment WHERE batch_payment_id IS NOT NULL')
        profile['linked_payments'] = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM ir_attachment WHERE res_model=%s", (MODEL,))
        profile['export_attachment_rows'] = cursor.fetchone()[0]
    stored_history = fingerprints(cursor, present_tables)
    stored_history.update(history_fingerprints(cursor))
    return {'models': models, 'fields': fields, 'selections': selections, 'xmlids': xmlids,
            'access': access, 'rules': rules, 'rule_groups': rule_groups, 'modules': owners,
            'incoming_relations': incoming, 'columns': columns, 'constraints': constraints,
            'relation_owners': relation_owners,
            'views': views, 'actions': actions, 'sequences': sequences, 'counters': counters,
            'stored_history': stored_history, 'profile': profile}


def assess(contract):
    """Facts and unmet gates; metadata presence never certifies a real engine."""
    fields = {(row['model'], row['name']): row for row in contract['fields']}
    blockers = []
    batch = next((row for row in contract['models'] if row['model'] == MODEL), None)
    if not batch:
        blockers.append('BATCH_MODEL_PROVIDER_ABSENT')
    if 'account_batch_payment' not in contract['stored_history']:
        blockers.append('ORIGINAL_BATCH_STORAGE_ABSENT')
    link = fields.get(('account.payment', 'batch_payment_id'))
    if not link or (link['ttype'], link.get('relation'), link.get('store')) != ('many2one', MODEL, True):
        blockers.append('ORIGINAL_PAYMENT_BATCH_RELATION_ABSENT_OR_CHANGED')
    native = [row['name'] for row in contract['modules'] if row['state'] == 'installed' and row['license'] == 'OEEL-1']
    if 'account_batch_payment' in native:
        blockers.append('BATCH_ENGINE_STILL_ENTERPRISE')
    if 'account_accountant_batch_payment' in native:
        blockers.append('BANK_RECONCILIATION_BRIDGE_STILL_ENTERPRISE')
    if not contract['profile']['linked_payments']:
        blockers.append('NO_LINKED_BATCH_HISTORY_REFERENCE')
    blockers += ['FUNCTIONAL_COMMUNITY_PROVIDER_NOT_CERTIFIED', 'COLD_IDENTITY_ADOPTION_NOT_EXECUTED']
    return {'preflight_only': True, 'conversion_ready': False, 'dependencies_may_change': False,
            'batch_model_id': batch['id'] if batch else None,
            'stored_monetary_fields': sorted(row['name'] for row in contract['fields']
                if row['model'] == MODEL and row['ttype'] == 'monetary' and row['store']),
            'state_keys': sorted(row['value'] for row in contract['selections']
                if row['field_id'] == fields.get((MODEL, 'state'), {}).get('id')),
            'incoming_models': sorted({row['model'] for row in contract['incoming_relations']}),
            'metadata_xmlids': len(contract['xmlids']), 'blockers': blockers,
            'registry_attributes_not_obtained_by_sql': ['model._auto', 'monetary.currency_field', 'binary.attachment',
                'computed_field.dependencies', 'workflow_methods', 'reconciliation_workflow']}


def compare(before, after):
    """Require every original identity/ACL/value/counter; allow new metadata rows."""
    differences = []
    for section in ('models', 'fields', 'selections', 'xmlids', 'access', 'rules', 'actions', 'sequences', 'relation_owners'):
        now = {row['id']: row for row in after[section]}
        for row in before[section]:
            got = now.get(row['id'])
            expected = dict(row)
            if section == 'xmlids' and got and row['module'] in NATIVE_MODULES + OWN_MODULES and (
                    row.get('noupdate') is False and got.get('noupdate') is True):
                expected['noupdate'] = True
            if got != expected:
                differences.append({'section': section, 'id': row['id'], 'missing': got is None})
    for section in ('columns', 'constraints', 'rule_groups'):
        for row in before[section]:
            if row not in after[section]:
                differences.append({'section': section, 'original_row_not_retained': True})
    for section in ('stored_history', 'counters'):
        for name, row in before[section].items():
            if after[section].get(name) != row:
                differences.append({'section': section, 'name': name})
    original_views = {row['id']: row for row in before['views']}
    current_views = {row['id']: row for row in after['views']}
    for view_id, row in original_views.items():
        if current_views.get(view_id) != row:
            differences.append({'section': 'views', 'id': view_id})
    return {'original_contract_exact': not differences, 'differences': differences,
            'functional_conversion_certified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare-with', type=Path)
    parser.add_argument('--community-candidate', type=Path,
                        help='Explicitly licensed vendor module snapshot; inspect declarations, never import')
    args = parser.parse_args()
    database = validate_database(args.database)
    output = args.output.resolve()
    if PRIVATE_ROOT not in output.parents:
        raise ValueError('Keep private metadata evidence outside the repository under /opt/steps-validation')
    if output.exists():
        raise ValueError('Never replace earlier preflight evidence')
    if os.name != 'posix' or os.geteuid() != 0:
        raise ValueError('Run as root on the documented database host; local peer authentication only')
    import pwd
    import psycopg2
    os.seteuid(pwd.getpwnam('postgres').pw_uid)
    try:
        connection = psycopg2.connect(dbname=database, user='postgres')
    finally:
        os.seteuid(0)
    try:
        connection.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with connection.cursor() as cursor:
            contract = collect(cursor)
        connection.rollback()
    finally:
        connection.close()
    proof = {'database': database, 'created_at_utc': datetime.now(timezone.utc).isoformat(),
             'read_only': True, 'orm_loaded': False, 'source_bodies_exported': False,
             'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'contract': contract, 'contract_sha256': digest(contract), 'assessment': assess(contract)}
    if args.community_candidate:
        candidate = licensed_candidate(args.community_candidate.resolve())
        candidate['same_technical_model_declared'] = any(row.get('_name') == MODEL for row in candidate['models'])
        candidate['direct_replacement_certified'] = False
        proof['community_candidate'] = candidate
    if args.compare_with:
        baseline = json.loads(args.compare_with.read_text())
        proof['comparison'] = compare(baseline['contract'], contract)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, default=str))
    os.chmod(output, 0o600)
    print(json.dumps({'output': str(output), 'assessment': proof['assessment'],
                      'comparison': proof.get('comparison')}))


if __name__ == '__main__':
    main()
