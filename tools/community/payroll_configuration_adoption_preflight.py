"""Readonly identity/ACL/translation gate for a sealed original payroll capsule.

No Odoo, import, permission grant, template read, rule evaluation or payroll
history. SQL never returns formula bodies; sealed source values remain opaque
and are never written to output. Evidence contains hashes and metadata only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess


TABLES = {
    'hr_payroll_structure': 'hr.payroll.structure',
    'hr_payroll_structure_type': 'hr.payroll.structure.type',
    'hr_payslip_input_type': 'hr.payslip.input.type',
    'hr_salary_rule': 'hr.salary.rule',
    'hr_salary_rule_category': 'hr.salary.rule.category',
}
EXTERNAL = {
    'res_company': ('res.company', ('id', 'currency_id')),
    'res_country': ('res.country', ('id', 'code')),
    'res_users': ('res.users', ('id', 'active', 'share')),
    'res_partner': ('res.partner', ('id', 'active', 'company_id')),
    'resource_calendar': ('resource.calendar', ('id', 'company_id', 'tz', 'two_weeks_calendar', 'flexible_hours')),
    'hr_work_entry_type': ('hr.work.entry.type', ('id', 'code', 'active', 'is_leave')),
    'ir_act_report_xml': ('ir.actions.report', ('id', 'model', 'report_type', 'report_name', 'binding_model_id')),
    'account_journal': ('account.journal', ('id', 'company_id', 'type', 'currency_id', 'active', 'code')),
    'account_account': ('account.account', ('id', 'active', 'deprecated', 'account_type', 'reconcile')),
    'account_analytic_account': ('account.analytic.account', ('id', 'company_id', 'active', 'plan_id')),
}
ROLES = {
    'user': ('hr_payroll.group_hr_payroll_user', 'payroll.group_payroll_user'),
    'manager': ('hr_payroll.group_hr_payroll_manager', 'payroll.group_payroll_manager'),
    'internal': ('base.group_user', 'base.group_user'),
}
OPERATIONS = ('read', 'write', 'create', 'unlink')


class PreflightError(ValueError):
    """Code-only: never interpolate raw configuration, text or formulas."""


def require(value, code):
    if not value:
        raise PreflightError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def identifier(value):
    require(re.fullmatch(r'[a-z_][a-z0-9_]*', value), 'unsafe-sql-identifier')
    return '"' + value + '"'


def capsule_rows(capsule):
    rows = {}
    require(capsule.get('schema') == 1 and capsule.get('read_only') is True, 'capsule-schema-or-mode')
    for flag in ('orm_loaded', 'rules_evaluated', 'historical_payroll_read', 'engine_converted',
                 'financial_certified', 'import_authorized_by_capsule'):
        require(capsule.get(flag) is False, 'capsule-not-a-readonly-unconverted-source')
    require(not capsule.get('unresolved_company_properties'), 'unresolved-source-company-properties')
    relations = set(capsule.get('relations', []))
    require(relations <= {'hr_payroll_structure_hr_payslip_input_type_rel'}, 'unsupported-configuration-relation')
    require(set(capsule['tables']) == set(TABLES) | relations, 'capsule-table-set')
    for table, data in capsule['tables'].items():
        require(len(data['rows_json']) == data['row_count'] and hashlib.sha256(
            '\n'.join(data['rows_json']).encode()).hexdigest() == data['rows_sha256'], 'capsule-row-digest')
        require(all(fk['validated'] for fk in data.get('foreign_keys', [])), 'unvalidated-original-relation')
    for table, model in TABLES.items():
        data = capsule['tables'][table]
        raw = data['rows_json']
        require(data['model'] == model and len(raw) == data['row_count'], 'capsule-table-contract')
        require(hashlib.sha256('\n'.join(raw).encode()).hexdigest() == data['rows_sha256'], 'capsule-row-digest')
        decoded = [json.loads(value) for value in raw]
        require(all(type(row.get('id')) is int and row['id'] > 0 for row in decoded), 'capsule-id-type')
        require(len({row['id'] for row in decoded}) == len(decoded), 'capsule-duplicate-id')
        rows[table] = decoded
    require(len({(row['module'], row['name']) for row in capsule['xmlids']}) == len(capsule['xmlids']),
            'capsule-duplicate-xmlid')
    ids = {model: {row['id'] for row in rows[table]} for table, model in TABLES.items()}
    require(all(row['model'] in ids and row['res_id'] in ids[row['model']] for row in capsule['xmlids']),
            'capsule-dangling-xmlid')
    return rows


def xmlid_selector(rows):
    return '(' + ','.join('(' + literal(row['module']) + ',' + literal(row['name']) + ')' for row in rows) + ')'


def queries(capsule, *, source=False):
    models = ','.join(map(literal, TABLES.values()))
    tables = ','.join(map(literal, list(TABLES) + list(EXTERNAL)
                         + ['hr_structure_salary_rule_rel', 'resource_calendar_attendance']))
    result = {
        'transaction': "SELECT current_setting('transaction_read_only') AS mode",
        'modules': "SELECT name,latest_version,license,to_jsonb(m)->'demo' AS demo FROM ir_module_module m WHERE state='installed' ORDER BY name",
        'columns': 'SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns '
                   "WHERE table_schema='public' AND table_name IN (" + tables + ') ORDER BY table_name,ordinal_position',
        'fields': 'SELECT id,model,name,ttype,relation,relation_field,required,readonly,store,related,'
                  'company_dependent,translate,on_delete FROM ir_model_fields WHERE model IN (' + models + ') ORDER BY model,name',
        # Technical keys/order only: no translated labels or formula bodies.
        'selection_values': 'SELECT f.model,f.name,s.value,s.sequence FROM ir_model_fields_selection s '
                            'JOIN ir_model_fields f ON f.id=s.field_id WHERE f.model IN (' + models
                            + ") AND f.ttype='selection' ORDER BY f.model,f.name,s.sequence,s.value",
        'field_groups': 'SELECT f.model,f.name,g.group_id FROM ir_model_fields_group_rel g JOIN ir_model_fields f ON f.id=g.field_id '
                        'WHERE f.model IN (' + models + ') ORDER BY f.model,f.name,g.group_id',
        'xmlids': 'SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE model IN (' + models
                   + ') OR (module,name) IN ' + xmlid_selector(capsule['xmlids']) + ' ORDER BY module,name',
        'acl': 'SELECT a.id,m.model,a.group_id,a.active,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink '
               'FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id WHERE m.model IN (' + models + ') ORDER BY m.model,a.id',
        'rules': 'SELECT r.id,m.model,r.domain_force,r.global,r.active,r.perm_read,r.perm_write,r.perm_create,r.perm_unlink '
                 'FROM ir_rule r JOIN ir_model m ON m.id=r.model_id WHERE m.model IN (' + models + ') ORDER BY m.model,r.id',
        'rule_groups': 'SELECT g.rule_group_id,g.group_id FROM rule_group_rel g JOIN ir_rule r ON r.id=g.rule_group_id '
                       'JOIN ir_model m ON m.id=r.model_id WHERE m.model IN (' + models + ') ORDER BY g.rule_group_id,g.group_id',
        'group_aliases': "SELECT module,name,res_id FROM ir_model_data WHERE model='res.groups' ORDER BY module,name",
        'implied_groups': 'SELECT gid,hid FROM res_groups_implied_rel ORDER BY gid,hid',
        'languages': 'SELECT code,active FROM res_lang ORDER BY code',
    }
    for table in TABLES:
        result['rows:' + table] = ('SELECT r.id,encode(sha256(convert_to(to_jsonb(r)::text,\'UTF8\')),\'hex\') AS row_sha256 '
                                  'FROM ' + identifier(table) + ' r ORDER BY r.id')
        result['source_hash:' + table] = ("SELECT encode(sha256(convert_to(coalesce(string_agg(to_jsonb(r)::text,E'\\n' ORDER BY r.id),''),'UTF8')),'hex') AS rows_sha256 FROM "
                                         + identifier(table) + ' r')
    if source:
        for table in capsule.get('relations', []):
            result['source_hash:' + table] = ("SELECT encode(sha256(convert_to(coalesce(string_agg(to_jsonb(r)::text,E'\\n' ORDER BY to_jsonb(r)::text),''),'UTF8')),'hex') AS rows_sha256 FROM "
                                             + identifier(table) + ' r')
    return result


def run_snapshot(database, statements):
    require(re.fullmatch(r'(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', database),
            'private-database-required')
    sql = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name, query in statements.items():
        require(query.lstrip().upper().startswith('SELECT '), 'select-only-query')
        sql.append('SELECT jsonb_build_object(\'section\',' + literal(name)
                   + ",'rows',coalesce(jsonb_agg(t),'[]'::jsonb)) FROM (" + query + ') t;')
    sql.append('ROLLBACK;')
    command = (['sudo', '-u', 'postgres'] if hasattr(os, 'geteuid') and os.geteuid() == 0 else [])
    command += ['env', 'PGOPTIONS=-c default_transaction_read_only=on', 'psql', '-XAtq',
                '-v', 'ON_ERROR_STOP=1', '-d', database]
    result = subprocess.run(command, input='\n'.join(sql), capture_output=True, text=True, check=True)
    decoded = [json.loads(line) for line in result.stdout.splitlines() if line]
    sections = {row['section']: row['rows'] for row in decoded}
    require(len(sections) == len(statements) == len(decoded), 'incomplete-metadata-snapshot')
    if 'transaction' in statements:
        require(sections['transaction'] == [{'mode': 'on'}], 'not-readonly')
    return sections


def external_ids(capsule):
    result = {name: set() for name in EXTERNAL}
    for reference in capsule['external_references'].values():
        require(reference['target'] in EXTERNAL, 'unknown-external-reference-model')
        result[reference['target']].update(reference.get('ids', []))
        result['res_company'].update(reference.get('company_ids', []))
    return result


def external_queries(capsule, metadata, source_external=None):
    statements = {}
    columns = {}
    for row in metadata['columns']:
        columns.setdefault(row['table_name'], set()).add(row['column_name'])
    for table, ids in external_ids(capsule).items():
        if not ids:
            continue
        require(all(type(value) is int and value > 0 for value in ids), 'external-id-type')
        model, allowed = EXTERNAL[table]
        selected = [name for name in allowed if name in columns.get(table, set())]
        require('id' in selected, 'missing-external-table')
        where = ' WHERE r.id=ANY(ARRAY[' + ','.join(map(str, sorted(ids))) + '])'
        fields = ','.join('r.' + identifier(name) for name in selected)
        statements['external:' + table] = 'SELECT ' + fields + ' FROM ' + identifier(table) + ' r' + where + ' ORDER BY r.id'
        statement = ('SELECT module,name,model,res_id FROM ir_model_data WHERE (model='
            + literal(model) + ' AND res_id=ANY(ARRAY[' + ','.join(map(str, sorted(ids))) + ']))')
        origin_aliases = (source_external or {}).get('external_aliases:' + table, [])
        if origin_aliases:
            statement += ' OR (module,name) IN ' + xmlid_selector(origin_aliases)
        statements['external_aliases:' + table] = statement + ' ORDER BY module,name'
        if table == 'res_company':
            # Company names/VAT remain hashes. No user login/password/partner
            # contact data, credentials, bank balances or documents are read.
            statements['company_identity'] = ("SELECT r.id,encode(sha256(convert_to(coalesce(p.name,''),'UTF8')),'hex') AS name_sha256,"
                "encode(sha256(convert_to(coalesce(p.vat,''),'UTF8')),'hex') AS vat_sha256,p.country_id "
                'FROM res_company r JOIN res_partner p ON p.id=r.partner_id' + where + ' ORDER BY r.id')
        if table == 'resource_calendar':
            allowed = ('calendar_id','dayofweek','hour_from','hour_to','day_period','week_type',
                       'date_from','date_to','resource_id','display_type')
            selected_attendance = [name for name in allowed if name in columns.get('resource_calendar_attendance', set())]
            require('calendar_id' in selected_attendance, 'missing-calendar-attendance-contract')
            statements['calendar_attendance'] = ('SELECT calendar_id,encode(sha256(convert_to(to_jsonb(x)::text,\'UTF8\')),\'hex\') AS semantics_sha256 FROM '
                '(SELECT ' + ','.join(map(identifier, selected_attendance)) + ' FROM resource_calendar_attendance '
                'WHERE calendar_id=ANY(ARRAY[' + ','.join(map(str, sorted(ids))) + '])) x ORDER BY calendar_id,semantics_sha256')
    reports = sorted(external_ids(capsule)['ir_act_report_xml'])
    if reports:
        statements['report_actions'] = ('SELECT id,type FROM ir_actions WHERE id=ANY(ARRAY['
            + ','.join(map(str, reports)) + ']) ORDER BY id')
    if {'struct_id', 'rule_id'} <= columns.get('hr_structure_salary_rule_rel', set()):
        statements['structure_rule_pairs'] = 'SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel ORDER BY struct_id,rule_id'
    return statements


def closure(role, edges):
    found, pending = set(), [role]
    while pending:
        current = pending.pop()
        if current in found:
            continue
        found.add(current)
        pending.extend(row['hid'] for row in edges if row['gid'] == current)
    return found


def effective_acl(metadata, xmlid, model):
    groups = {row['module'] + '.' + row['name']: row['res_id'] for row in metadata['group_aliases']}
    if xmlid not in groups:
        return None
    inherited = closure(groups[xmlid], metadata['implied_groups'])
    rows = [row for row in metadata['acl'] if row['model'] == model and row['active']
            and (row['group_id'] is None or row['group_id'] in inherited)]
    return {operation: any(row['perm_' + operation] for row in rows) for operation in OPERATIONS}


def field_visible_to_role(metadata, xmlid, model, name):
    aliases = {row['module'] + '.' + row['name']: row['res_id'] for row in metadata['group_aliases']}
    if xmlid not in aliases:
        return None
    allowed = {row['group_id'] for row in metadata['field_groups'] if (row['model'], row['name']) == (model, name)}
    return not allowed or bool(allowed & closure(aliases[xmlid], metadata['implied_groups']))


def selection_differences(source, target):
    """A Selection declaration alone does not preserve its stored value keys.

    Metadata cannot certify callable runtime choices. Empty catalogues stay an
    explicit unknown rather than passing because two empty lists compare equal.
    """
    result = []
    for field in source['fields']:
        if field['ttype'] != 'selection':
            continue
        key = field['model'], field['name']
        choices = []
        for metadata in (source, target):
            rows = [row for row in metadata.get('selection_values', [])
                    if (row['model'], row['name']) == key]
            choices.append([row['value'] for row in sorted(rows, key=lambda row: (row['sequence'], row['value']))])
        before, after = choices
        if before != after or not before:
            result.append({'model': key[0], 'field': key[1],
                'missing_target_values': sorted(set(before) - set(after)),
                'target_only_values': sorted(set(after) - set(before)),
                'shared_order_differs': [value for value in before if value in after]
                    != [value for value in after if value in before],
                'source_catalogue_empty': not before, 'target_catalogue_empty': not after,
                'runtime_choices_certified': False})
    return result


def assess(capsule, source, target, source_external, target_external):
    rows = capsule_rows(capsule)
    occupied, xmlid_conflicts, field_differences, acl_differences, field_group_differences = [], [], [], [], []
    source_fields = {(row['model'], row['name']): row for row in source['fields']}
    target_fields = {(row['model'], row['name']): row for row in target['fields']}
    source_columns = {(row['table_name'], row['column_name']): row for row in source.get('columns', [])}
    target_columns = {(row['table_name'], row['column_name']): row for row in target.get('columns', [])}
    column_differences = []
    for key, column in source_columns.items():
        if key[0] not in TABLES:
            continue
        other = target_columns.get(key)
        changes = ['missing'] if other is None else [name for name in ('data_type','is_nullable') if column[name] != other[name]]
        if changes:
            column_differences.append({'table': key[0], 'field': key[1], 'differences': changes})
    capsule_metadata_matches = True
    attribute_map = {'type': 'ttype', 'relation': 'relation', 'required': 'required', 'readonly': 'readonly',
                     'store': 'store', 'related': 'related', 'company_dependent': 'company_dependent'}
    for field in capsule.get('field_metadata', []):
        live = source_fields.get((field['model'],field['name']), {})
        if any(field[name] != live.get(destination) for name,destination in attribute_map.items()):
            capsule_metadata_matches = False
    for table, records in rows.items():
        target_rows = {row['id']: row for row in target['rows:' + table]}
        raw_hashes = {json.loads(raw)['id']: hashlib.sha256(raw.encode()).hexdigest()
                      for raw in capsule['tables'][table]['rows_json']}
        for row in records:
            if row['id'] in target_rows:
                occupied.append({'model': TABLES[table], 'source_id': row['id'],
                    'strict_sql_row_equal': raw_hashes[row['id']] == target_rows[row['id']]['row_sha256'],
                    'overwrite_authorized': False})
    by_xmlid = {(row['module'], row['name']): row for row in target['xmlids']}
    for row in capsule['xmlids']:
        other = by_xmlid.get((row['module'], row['name']))
        if other and (other['model'], other['res_id'], other['noupdate']) != (row['model'], row['res_id'], row['noupdate']):
            xmlid_conflicts.append({'xmlid': row['module'] + '.' + row['name'], 'model': row['model'],
                'source_id': row['res_id'], 'target_model': other['model'], 'target_id': other['res_id'],
                'noupdate_differs': row['noupdate'] != other['noupdate']})
    attributes = ('ttype', 'relation', 'required', 'readonly', 'store', 'related', 'company_dependent', 'translate', 'on_delete')
    for key, field in source_fields.items():
        other = target_fields.get(key)
        differences = ['missing'] if other is None else [name for name in attributes if field[name] != other[name]]
        if differences:
            field_differences.append({'model': key[0], 'field': key[1], 'differences': differences})
    for role, (native_name, community_name) in ROLES.items():
        for model in TABLES.values():
            before, after = effective_acl(source, native_name, model), effective_acl(target, community_name, model)
            if before != after or before is None:
                acl_differences.append({'role': role, 'model': model, 'source': before, 'target': after,
                    'grants_authorized': False})
        for model, name in sorted(set(source_fields) & set(target_fields)):
            before = field_visible_to_role(source, native_name, model, name)
            after = field_visible_to_role(target, community_name, model, name)
            if before != after or before is None:
                field_group_differences.append({'role': role, 'model': model, 'field': name,
                                               'source_visible': before, 'target_visible': after})
    properties = []
    for name, reference in capsule['external_references'].items():
        if not reference.get('company_dependent'):
            continue
        table, field_name = name.split('.', 1)
        mappings, nulls, slots, source_owner_issues, target_owner_issues = 0, 0, 0, [], []
        expected_values = []
        source_masters = {row['id']: row for row in source_external.get('external:' + reference['target'], [])}
        target_masters = {row['id']: row for row in target_external.get('external:' + reference['target'], [])}
        target_companies = {row['id'] for row in target_external.get('external:res_company', [])}
        for row in rows[table]:
            value = row.get(field_name)
            if value is None:
                nulls += 1
                continue
            require(isinstance(value, dict), 'company-property-must-remain-object-or-null')
            mappings += 1
            for company, master in value.items():
                require(re.fullmatch(r'[1-9][0-9]*', company) and (master is None or type(master) is int and master > 0),
                        'company-property-key-or-value')
                company = int(company); slots += 1
                expected_values.append({'id': row['id'], 'company_id': company, 'value': master})
                if reference['target'] == 'account_journal' and master is not None:
                    if source_masters.get(master, {}).get('company_id') != company:
                        source_owner_issues.append({'source_id': row['id'], 'company_id': company, 'master_id': master})
                    if company not in target_companies or target_masters.get(master, {}).get('company_id') != company:
                        target_owner_issues.append({'source_id': row['id'], 'company_id': company, 'master_id': master})
        order = lambda item: (item['id'], item['company_id'])
        require(sorted(expected_values, key=order) == sorted(reference['original_values'], key=order), 'company-property-capsule-reference-drift')
        properties.append({'field': name, 'null_rows': nulls, 'mapping_rows': mappings, 'value_slots': slots,
            'source_owner_issues': source_owner_issues, 'target_owner_issues': target_owner_issues,
            'scalarization_permitted': False, 'adopted': False})
    translations = []
    for table, field in (('hr_payslip_input_type', 'name'), ('hr_salary_rule', 'note')):
        values = [row.get(field) for row in rows[table]]
        translations.append({'model': TABLES[table], 'field': field, 'null_rows': sum(value is None for value in values),
            'scalar_rows': sum(isinstance(value, str) for value in values),
            'object_rows': sum(isinstance(value, dict) for value in values),
            'languages': sorted({language for value in values if isinstance(value, dict) for language in value}),
            'source_translate': source_fields[(TABLES[table], field)]['translate'],
            'target_translate': target_fields.get((TABLES[table], field), {}).get('translate'),
            'literal_base_language_policy_approved': False})
    external = []
    for table, ids in external_ids(capsule).items():
        present = {row['id'] for row in target_external.get('external:' + table, [])}
        source_aliases = {(row['module'], row['name']): row for row in source_external.get('external_aliases:' + table, [])}
        target_aliases = {(row['module'], row['name']): row for row in target_external.get('external_aliases:' + table, [])}
        collisions = []
        for key, row in source_aliases.items():
            other = target_aliases.get(key)
            if other and (other['model'], other['res_id']) != (row['model'], row['res_id']):
                collisions.append({'xmlid': '.'.join(key), 'source_id': row['res_id'], 'target_id': other['res_id']})
        native = {row['id']: dict(row) for row in source_external.get('external:' + table, [])}
        destination = {row['id']: dict(row) for row in target_external.get('external:' + table, [])}
        if table == 'res_company':
            for row in source_external.get('company_identity', []):
                native.setdefault(row['id'], {}).update(row)
            for row in target_external.get('company_identity', []):
                destination.setdefault(row['id'], {}).update(row)
        differences = []
        for source_id in sorted(ids & set(native) & set(destination)):
            left, right = native[source_id], destination[source_id]
            changed = sorted(name for name in set(left) | set(right) if left.get(name) != right.get(name))
            if changed:
                differences.append({'source_id': source_id, 'fields': changed})
        if table == 'resource_calendar':
            for source_id in sorted(ids):
                left = sorted(row['semantics_sha256'] for row in source_external.get('calendar_attendance', []) if row['calendar_id'] == source_id)
                right = sorted(row['semantics_sha256'] for row in target_external.get('calendar_attendance', []) if row['calendar_id'] == source_id)
                if left != right:
                    differences.append({'source_id': source_id, 'fields': ['attendance_semantics']})
        external.append({'table': table, 'source_ids': sorted(ids), 'missing_target_ids': sorted(ids - present),
                         'alias_collisions': collisions, 'metadata_identity_differences': differences,
                         'numeric_presence_proves_identity': False, 'adopted': False})
    report_conflicts = [row for row in target_external.get('report_actions', []) if row['type'] != 'ir.actions.report']
    source_matches = all(source['source_hash:' + table][0]['rows_sha256'] == data['rows_sha256'] for table,data in capsule['tables'].items())
    expected_pairs = [(row.get('struct_id'), row['id']) for row in rows['hr_salary_rule'] if row.get('struct_id') is not None]
    actual_pairs = {(row['struct_id'],row['rule_id']) for row in target_external.get('structure_rule_pairs', [])}
    for table, data in capsule['tables'].items():
        for fk in data.get('foreign_keys', []):
            if fk['target'] in rows and table in rows:
                ids = {row['id'] for row in rows[fk['target']]}
                require(all(row.get(fk['column']) is None or row[fk['column']] in ids for row in rows[table]),
                        'broken-original-internal-configuration-reference')
    target_is_community = not any(row.get('license') == 'OEEL-1' for row in target.get('modules', []))
    return {'source_capsule_matches_live_configuration': source_matches,
        'source_capsule_field_metadata_matches': capsule_metadata_matches,
        'target_has_zero_enterprise': target_is_community,
        'source_master_count': sum(len(value) for value in rows.values()), 'source_xmlid_count': len(capsule['xmlids']),
        'occupied_source_ids': occupied, 'xmlid_conflicts': xmlid_conflicts, 'field_differences': field_differences,
        'selection_value_differences': selection_differences(source, target),
        'selection_contract_runtime_certified': False,
        'column_differences': column_differences,
        'target_only_company_fields': [{'model': model, 'field': name, 'explicit_null_required_for_originals': True}
            for model in ('hr.payroll.structure', 'hr.salary.rule', 'hr.salary.rule.category')
            for name in ('company_id',) if (model, name) not in source_fields and (model, name) in target_fields],
        'role_acl_differences': acl_differences, 'field_group_differences': field_group_differences,
        'record_rule_equivalence_certified': False,
        'company_properties': properties, 'translations': translations,
        'external_references': external, 'report_action_type_conflicts': report_conflicts,
        'structure_rule_projection': {'original_scalar_pairs': len(expected_pairs), 'target_pairs': len(actual_pairs),
            'original_pairs_numerically_present': len(set(expected_pairs) & actual_pairs),
            'numeric_pair_presence_proves_identity': False},
        'source_security_sha256': digest({name: source[name] for name in ('acl', 'rules', 'rule_groups', 'group_aliases', 'implied_groups', 'field_groups')}),
        'target_security_sha256': digest({name: target[name] for name in ('acl', 'rules', 'rule_groups', 'group_aliases', 'implied_groups', 'field_groups')}),
        'adoption_ready': False, 'reference_target_only': True, 'import_authorized': False,
        'permissions_expanded': False, 'orm_loaded': False, 'rules_evaluated': False,
        'salary_formulas_exposed': False, 'historical_payroll_read': False,
        'remaining_gates': ['new-target-without-demo-and-original-id-collisions', 'external-master-and-report-identity',
                            'translation-and-NULL-policy', 'explicit-role-ACL-and-country-company-rule-acceptance',
                            'complete-source-configuration-and-financial-certification']}


def compare_reports(before, after):
    parts = ('source_metadata', 'target_metadata', 'source_external_metadata', 'target_external_metadata')
    changed = [part for part in parts if before[part] != after[part]]
    provenance = ('capsule_sha256', 'source_database', 'target_database', 'tool_sha256')
    changed.extend(name for name in provenance if before[name] != after[name])
    return {'read_only_evidence_unchanged': not changed, 'changed_sections': sorted(changed),
            'before_sha256': digest({part: before[part] for part in parts}),
            'after_sha256': digest({part: after[part] for part in parts})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capsule', type=Path, required=True)
    parser.add_argument('--expected-capsule-sha256', required=True)
    parser.add_argument('--target-database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    require(stat.S_IMODE(args.capsule.stat().st_mode) == 0o600, 'capsule-must-be-private-0600')
    encoded = args.capsule.read_bytes()
    require(hashlib.sha256(encoded).hexdigest() == args.expected_capsule_sha256, 'capsule-seal-mismatch')
    capsule = json.loads(encoded)
    capsule_rows(capsule)
    require(args.target_database.startswith('COMMUNITY_PAYROLL_API_'), 'community-private-reference-required')
    require(capsule['database'].startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_'), 'native-private-source-required')
    output = args.output.resolve()
    require(args.output.is_absolute() and Path(__file__).resolve().parents[2] not in output.parents,
            'private-output-outside-checkout-required')
    source, target = run_snapshot(capsule['database'], queries(capsule, source=True)), run_snapshot(args.target_database, queries(capsule))
    source_external = run_snapshot(capsule['database'], external_queries(capsule, source))
    target_external = run_snapshot(args.target_database, external_queries(capsule, target, source_external))
    assessment = assess(capsule, source, target, source_external, target_external)
    report = {'capsule_sha256': args.expected_capsule_sha256, 'source_database': capsule['database'],
        'target_database': args.target_database, 'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_metadata': source, 'target_metadata': target, 'source_external_metadata': source_external,
        'target_external_metadata': target_external, 'assessment': assessment}
    if args.baseline:
        report['read_only_comparison'] = compare_reports(json.loads(args.baseline.read_text()), report)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'source_master_count': assessment['source_master_count'],
        'occupied_source_ids': len(assessment['occupied_source_ids']), 'xmlid_conflicts': len(assessment['xmlid_conflicts']),
        'field_differences': len(assessment['field_differences']), 'role_acl_differences': len(assessment['role_acl_differences']),
        'selection_value_differences': len(assessment['selection_value_differences']),
        'report_action_type_conflicts': len(assessment['report_action_type_conflicts']), 'adoption_ready': False,
        'salary_formulas_exposed': False}))
    return 0 if (assessment['source_capsule_matches_live_configuration']
        and assessment['source_capsule_field_metadata_matches'] and assessment['target_has_zero_enterprise']
        and report.get('read_only_comparison', {}).get('read_only_evidence_unchanged', True)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
