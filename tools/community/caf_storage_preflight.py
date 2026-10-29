"""Read-only CAF identity/storage gate for existing private database copies.

Does not import Odoo, read CAF/certificate/key payloads, load Enterprise source,
reserve folios, restore counters or write to PostgreSQL. The result deliberately
blocks adoption until the native allocation/API and real trust evidence close.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


MODEL = 'l10n_cl.dte.caf'
TABLE = 'l10n_cl_dte_caf'
FIELDS = {
    'id': ('integer', None, True), 'display_name': ('char', None, False),
    'caf_file': ('binary', None, True), 'filename': ('char', None, True),
    'issued_date': ('date', None, True), 'start_nb': ('integer', None, True),
    'final_nb': ('integer', None, True), 'status': ('selection', None, True),
    'company_id': ('many2one', 'res.company', True),
    'l10n_latam_document_type_id': ('many2one', 'l10n_latam.document.type', True),
    'create_uid': ('many2one', 'res.users', True),
    'write_uid': ('many2one', 'res.users', True),
    'create_date': ('datetime', None, True), 'write_date': ('datetime', None, True),
}
SQL = {
    'transaction': "SELECT current_setting('transaction_read_only') AS read_only",
    'providers': """SELECT name,latest_version,license,state FROM ir_module_module
        WHERE name IN ('l10n_cl','l10n_cl_edi','l10n_cl_edi_stock','l10n_cl_edi_exports',
        'certificate','account_edi','step_l10n_cl_edi_core') ORDER BY name""",
    'models': "SELECT id,model,state FROM ir_model WHERE model='l10n_cl.dte.caf' ORDER BY id",
    'fields': """SELECT id,name,model,ttype,relation,relation_field,store,required,readonly,
        state,related,depends,on_delete,domain,compute IS NOT NULL AND compute<>'' AS compute_metadata_present
        FROM ir_model_fields WHERE model='l10n_cl.dte.caf' ORDER BY name""",
    'selections': """SELECT s.id,f.name AS field,s.value,s.sequence FROM ir_model_fields_selection s
        JOIN ir_model_fields f ON f.id=s.field_id WHERE f.model='l10n_cl.dte.caf'
        ORDER BY f.name,s.sequence,s.id""",
    'columns': """SELECT column_name,data_type,is_nullable,column_default FROM information_schema.columns
        WHERE table_schema='public' AND table_name='l10n_cl_dte_caf' ORDER BY ordinal_position""",
    'constraints': """SELECT conname,contype,pg_get_constraintdef(oid) AS definition
        FROM pg_constraint WHERE conrelid='l10n_cl_dte_caf'::regclass ORDER BY conname""",
    'relations': """SELECT conrelid::regclass::text AS source,confrelid::regclass::text AS target,
        conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE contype='f'
        AND (conrelid='l10n_cl_dte_caf'::regclass OR confrelid='l10n_cl_dte_caf'::regclass)
        ORDER BY conname""",
    'inverse_fields': """SELECT id,model,name,ttype,relation,relation_field FROM ir_model_fields
        WHERE relation='l10n_cl.dte.caf' ORDER BY model,name""",
    'acl': """SELECT a.id,a.name,a.group_id,a.active,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink
        FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id WHERE m.model='l10n_cl.dte.caf'
        ORDER BY a.id""",
    'rules': """SELECT r.id,r.name,r.global,r.active,r.domain_force,r.perm_read,r.perm_write,
        r.perm_create,r.perm_unlink,coalesce((SELECT jsonb_agg(group_id ORDER BY group_id)
        FROM rule_group_rel WHERE rule_group_id=r.id),'[]'::jsonb) AS groups
        FROM ir_rule r JOIN ir_model m ON m.id=r.model_id WHERE m.model='l10n_cl.dte.caf' ORDER BY r.id""",
    'group_aliases': """SELECT module,name,res_id FROM ir_model_data WHERE model='res.groups'
        AND res_id IN (SELECT a.group_id FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
        WHERE m.model='l10n_cl.dte.caf') ORDER BY module,name""",
    'xmlids': """SELECT module,name,model,res_id,noupdate FROM ir_model_data WHERE
        (model='ir.model' AND res_id IN (SELECT id FROM ir_model WHERE model='l10n_cl.dte.caf')) OR
        (model='ir.model.fields' AND res_id IN (SELECT id FROM ir_model_fields WHERE model='l10n_cl.dte.caf')) OR
        (model='ir.model.fields.selection' AND res_id IN (SELECT s.id FROM ir_model_fields_selection s
          JOIN ir_model_fields f ON f.id=s.field_id WHERE f.model='l10n_cl.dte.caf')) OR
        (model='ir.model.access' AND res_id IN (SELECT a.id FROM ir_model_access a
          JOIN ir_model m ON m.id=a.model_id WHERE m.model='l10n_cl.dte.caf')) OR
        (model='ir.rule' AND res_id IN (SELECT r.id FROM ir_rule r
          JOIN ir_model m ON m.id=r.model_id WHERE m.model='l10n_cl.dte.caf')) OR
        (model='ir.ui.view' AND res_id IN (SELECT id FROM ir_ui_view WHERE model='l10n_cl.dte.caf'))
        OR (model='ir.actions.act_window' AND res_id IN
          (SELECT id FROM ir_act_window WHERE res_model='l10n_cl.dte.caf'))
        OR (model='ir.model.constraint' AND res_id IN (SELECT c.id FROM ir_model_constraint c
          JOIN ir_model m ON m.id=c.model WHERE m.model='l10n_cl.dte.caf'))
        ORDER BY module,name""",
    'views': """SELECT id,name,inherit_id,mode,active,priority,md5(arch_db::text) AS arch_hash
        FROM ir_ui_view WHERE model='l10n_cl.dte.caf' ORDER BY id""",
    'actions': """SELECT id,res_model,view_mode,target FROM ir_act_window
        WHERE res_model='l10n_cl.dte.caf' ORDER BY id""",
    'action_views': """SELECT id,act_window_id,view_id,view_mode,sequence FROM ir_act_window_view
        WHERE act_window_id IN (SELECT id FROM ir_act_window WHERE res_model='l10n_cl.dte.caf')
        ORDER BY act_window_id,sequence,id""",
    'constraint_registry': """SELECT c.id,c.name,c.model,c.type,c.module,m.name AS owner,m.license
        FROM ir_model_constraint c JOIN ir_model model ON model.id=c.model
        JOIN ir_module_module m ON m.id=c.module WHERE model.model='l10n_cl.dte.caf' ORDER BY c.id""",
    'caf_rows': """SELECT count(*) AS records,
        count(*) FILTER(WHERE company_id IS NULL) AS missing_company,
        count(*) FILTER(WHERE l10n_latam_document_type_id IS NULL) AS missing_document_type,
        count(*) FILTER(WHERE start_nb IS NULL OR final_nb IS NULL OR start_nb>final_nb) AS invalid_ranges,
        md5(coalesce(string_agg(row(id,filename,company_id,l10n_latam_document_type_id,start_nb,
          final_nb,status,issued_date,create_uid,write_uid,create_date,write_date)::text,
          E'\\n' ORDER BY id),'')) AS metadata_hash FROM l10n_cl_dte_caf""",
    'attachments': """SELECT count(*) AS records,
        count(*) FILTER(WHERE a.store_fname IS NOT NULL) AS filestore,
        count(*) FILTER(WHERE a.db_datas IS NOT NULL) AS database_storage,
        count(*) FILTER(WHERE a.public) AS public,
        count(*) FILTER(WHERE c.id IS NULL) AS orphan,
        md5(coalesce(string_agg(row(a.id,a.res_id,a.res_field,a.type,a.public,a.company_id,
          a.checksum,a.file_size,a.create_uid,a.write_uid,a.create_date,a.write_date)::text,
          E'\\n' ORDER BY a.id),'')) AS metadata_hash
        FROM ir_attachment a LEFT JOIN l10n_cl_dte_caf c ON c.id=a.res_id
        WHERE a.res_model='l10n_cl.dte.caf' AND a.res_field='caf_file'""",
    'id_counter': 'SELECT last_value,is_called FROM public.l10n_cl_dte_caf_id_seq',
    'document_fields': """SELECT id,model,name,ttype,relation,relation_field,store,related
        FROM ir_model_fields WHERE model IN ('account.move','stock.picking','account.journal')
        AND (name IN ('name','state','company_id','journal_id','sequence_number','sequence_prefix',
        'l10n_latam_document_type_id','l10n_latam_document_number') OR relation='l10n_cl.dte.caf')
        ORDER BY model,name""",
    'document_constraints': """SELECT conrelid::regclass::text AS model,conname,
        pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE contype='u'
        AND conrelid IN ('account_move'::regclass,'stock_picking'::regclass) ORDER BY conname""",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def assess(sections):
    """Check only facts evidenced by metadata; never infer native behavior."""
    errors = []
    def require(condition, message):
        if not condition:
            errors.append(message)
    require(sections.get('transaction') == [{'read_only': 'on'}], 'transaction-not-read-only')
    models = sections.get('models', [])
    require(len(models) == 1 and models[0].get('model') == MODEL, 'model-identity')
    fields = {row['name']: row for row in sections.get('fields', [])}
    require(set(fields) == set(FIELDS), 'field-set')
    for name, expected in FIELDS.items():
        actual = fields.get(name, {})
        require((actual.get('ttype'), actual.get('relation'), actual.get('store')) == expected,
                'field-contract:' + name)
    columns = {row['column_name'] for row in sections.get('columns', [])}
    require(columns == set(FIELDS) - {'caf_file', 'display_name'}, 'physical-column-set')
    types = {'integer': 'integer', 'char': 'character varying', 'selection': 'character varying',
             'many2one': 'integer', 'date': 'date', 'datetime': 'timestamp without time zone'}
    for row in sections.get('columns', []):
        name = row['column_name']
        require(name in FIELDS and row.get('data_type') == types.get(FIELDS.get(name, (None,))[0])
                and row.get('is_nullable') == ('NO' if name == 'id' else 'YES'),
                'physical-column-contract:' + name)
    require([(row.get('field'), row.get('value')) for row in sections.get('selections', [])]
            == [('status', 'in_use'), ('status', 'spent')], 'status-selection')
    require(any(row.get('contype') == 'u' and row.get('definition') == 'UNIQUE (filename)'
                for row in sections.get('constraints', [])), 'filename-unique')
    require(any(row.get('contype') == 'p' and row.get('definition') == 'PRIMARY KEY (id)'
                for row in sections.get('constraints', [])), 'primary-key')
    foreign_keys = {row.get('definition') for row in sections.get('relations', [])}
    require(foreign_keys == {
        'FOREIGN KEY (company_id) REFERENCES res_company(id) ON DELETE SET NULL',
        'FOREIGN KEY (create_uid) REFERENCES res_users(id) ON DELETE SET NULL',
        'FOREIGN KEY (write_uid) REFERENCES res_users(id) ON DELETE SET NULL',
        'FOREIGN KEY (l10n_latam_document_type_id) REFERENCES l10n_latam_document_type(id) ON DELETE SET NULL',
    }, 'foreign-key-contract')
    require(any((row.get('model'), row.get('name'), row.get('relation_field')) == (
                'l10n_latam.document.type', 'l10n_cl_dte_caf_ids', 'l10n_latam_document_type_id')
                for row in sections.get('inverse_fields', [])), 'document-type-inverse')
    aliases = {(row['module'], row['name']): row for row in sections.get('xmlids', [])}
    model_alias = aliases.get(('l10n_cl_edi', 'model_l10n_cl_dte_caf'), {})
    require(bool(models) and model_alias.get('model') == 'ir.model'
            and model_alias.get('res_id') == models[0]['id'], 'model-xmlid')
    for name, field in fields.items():
        alias = aliases.get(('l10n_cl_edi', 'field_l10n_cl_dte_caf__' + name), {})
        require(alias.get('model') == 'ir.model.fields' and alias.get('res_id') == field.get('id'),
                'field-xmlid:' + name)
    for selection in sections.get('selections', []):
        alias = aliases.get(('l10n_cl_edi', 'selection__l10n_cl_dte_caf__status__' + selection['value']), {})
        require(alias.get('model') == 'ir.model.fields.selection' and alias.get('res_id') == selection.get('id'),
                'selection-xmlid:' + selection['value'])
    acl = {row['id']: row for row in sections.get('acl', [])}
    groups = {(row['module'], row['name']): row['res_id'] for row in sections.get('group_aliases', [])}
    for owner, group in (('l10n_cl_edi', ('account', 'group_account_manager')),
                         ('l10n_cl_edi_stock', ('stock', 'group_stock_manager'))):
        alias = aliases.get((owner, 'access_dte_caf_manager'), {})
        row = acl.get(alias.get('res_id'), {})
        require(alias.get('model') == 'ir.model.access' and row.get('group_id') is not None
                and row.get('group_id') == groups.get(group) and row.get('active')
                and all(row.get('perm_' + operation) for operation in ('read', 'write', 'create', 'unlink')),
                'acl-contract:' + owner)
    require(len(acl) == 2, 'acl-set')
    rules = sections.get('rules', [])
    require(len(rules) == 1 and rules[0].get('global') and rules[0].get('active')
            and not rules[0].get('groups')
            and rules[0].get('domain_force') == "[('company_id', 'in', company_ids + [False])]"
            and all(rules[0].get('perm_' + operation) for operation in ('read', 'write', 'create', 'unlink')),
            'company-rule-contract')
    attachments = sections.get('attachments', [{}])[0]
    require(not attachments.get('public') and not attachments.get('orphan'), 'attachment-exposure-or-orphan')
    caf = sections.get('caf_rows', [{}])[0]
    require(not caf.get('invalid_ranges'), 'invalid-stored-range')
    counter = sections.get('id_counter', [])
    require(len(counter) == 1 and type(counter[0].get('is_called')) is bool
            and type(counter[0].get('last_value')) is int, 'id-counter-contract')
    blockers = ['native-folio-allocation-and-concurrency-not-proven',
                'native-provider-runtime-api-not-adopted',
                'official-authority-key-and-fingerprint-not-accepted',
                'payload-and-key-validation-not-performed',
                'binary-runtime-attachment-policy-not-introspected']
    if not caf.get('records'):
        blockers.append('no-real-caf-record-for-history-acceptance')
    if caf.get('missing_company') or caf.get('missing_document_type'):
        blockers.append('unassigned-existing-master-requires-explicit-policy')
    return {'metadata_contract_valid': not errors, 'errors': errors, 'blockers': blockers,
            'adoption_ready': False, 'folio_allocation_ready': False,
            'payload_read': False, 'enterprise_bodies_read': False,
            'storage_inference': 'binary-field-without-column; attachment-metadata-only',
            'caf_records': caf.get('records'), 'attachments': attachments.get('records'),
            'preservation_fingerprint_sha256': digest(sections)}


def compare(baseline, candidate):
    """Exact per-section comparison; no allowed drift or counter restoration."""
    before, after = baseline['sections'], candidate['sections']
    names = set(before) | set(after)
    changed = sorted(name for name in names if before.get(name) != after.get(name))
    return {'preserved': not changed, 'changed_sections': changed,
            'baseline_sha256': digest(before), 'candidate_sha256': digest(after)}


def read_metadata(database):
    # Commands are fixed SELECTs inside one server-enforced read-only snapshot.
    statements = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, query in SQL.items():
        statements.append("SELECT jsonb_build_object('section','" + name
            + "','rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    statements.append('ROLLBACK;')
    command = (['sudo', '-u', 'postgres'] if hasattr(os, 'geteuid') and os.geteuid() == 0 else [])
    command += ['env', 'PGOPTIONS=-c default_transaction_read_only=on',
                'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database]
    result = subprocess.run(command, input='\n'.join(statements), capture_output=True,
                            text=True, check=True)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line]
    sections = {row['section']: row['rows'] for row in rows}
    if len(rows) != len(SQL) or set(sections) != set(SQL):
        raise ValueError('Incomplete or duplicate metadata sections')
    return sections


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'MANAGEMENT_QA_(?:CERRO|SYS)_[A-Za-z0-9_]+', args.database):
        parser.error('Use an existing private Cerro/SyS copy; production is outside this preflight')
    output = args.output.resolve()
    checkout = Path(__file__).resolve().parents[2]
    if not args.output.is_absolute() or checkout in output.parents:
        parser.error('Evidence must use a private absolute path outside source checkouts')
    sections = read_metadata(args.database)
    report = {'database': args.database, 'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'sections': sections, 'assessment': assess(sections)}
    if args.baseline:
        report['preservation'] = compare(json.loads(args.baseline.read_text()), report)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'metadata_contract_valid': report['assessment']['metadata_contract_valid'],
                      'adoption_ready': False, 'caf_records': report['assessment']['caf_records'],
                      'preserved': report.get('preservation', {}).get('preserved')}))
    return 0 if report['assessment']['metadata_contract_valid'] and report.get('preservation', {}).get('preserved', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
