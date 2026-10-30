"""Exercise an anchored original cohort through the real Community registry.

Call ``run`` from the coordinator's already loaded, offline Odoo shell. This
module never starts Odoo, connects to another database, grants a role, creates
an actor, commits, evaluates a salary rule or reads payroll history. The sole
permitted write is the existing private structure/rule projection API. A
failure rolls back that API's writes and emits a code-only private receipt.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat

import payroll_configuration_adoption_preflight as gate


CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
DATABASE = r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+'
PRIVATE_ROOT = Path('/opt/steps-validation')
HISTORY_TABLES = {
    'hr_payslip', 'hr_payslip_line', 'hr_payslip_input',
    'hr_payslip_worked_days', 'hr_payslip_run', 'account_move',
    'account_move_line', 'account_partial_reconcile', 'account_full_reconcile',
}
FORMS = (
    ('hr.payroll.structure', 'payroll.hr_payroll_structure_view_form'),
    ('hr.payroll.structure.type', 'step_payroll_oca_api.payroll_structure_type_original_form'),
    ('hr.payslip.input.type', 'step_payroll_oca_api.original_input_type_form'),
    ('hr.salary.rule', 'payroll.hr_salary_rule_view_form'),
    ('hr.salary.rule.category', 'payroll.hr_salary_rule_category_view_form'),
)
MENUS = (
    ('payroll.hr_payroll_structure_menu', 'payroll.hr_payroll_structure_action', 'hr.payroll.structure'),
    ('payroll.menu_action_hr_salary_rule_form', 'payroll.action_salary_rule_form', 'hr.salary.rule'),
    ('payroll.menu_hr_salary_rule_category', 'payroll.hr_salary_rule_category_action', 'hr.salary.rule.category'),
    ('step_payroll_oca_api.original_input_type_menu', 'step_payroll_oca_api.original_input_type_action', 'hr.payslip.input.type'),
)


class ProbeBlocked(ValueError):
    """Only technical codes, never source values, rules or personal data."""


def require(value, code):
    if not value:
        raise ProbeBlocked(code)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode())


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z_][a-z0-9_]*', value), 'unsafe-identifier')
    return '"' + value + '"'


def sealed_json(path, expected):
    path = Path(path)
    require(path.is_absolute() and path.resolve().is_relative_to(PRIVATE_ROOT)
        and not path.is_symlink(), 'sealed-input-outside-private-root')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600,
        'sealed-input-must-be-regular-0600')
    raw = path.read_bytes()
    require(re.fullmatch(r'[a-f0-9]{64}', expected or '') and sha(raw) == expected,
        'sealed-input-sha256-mismatch')
    return json.loads(raw)


def source_alias_contract(capsule, identity):
    """Distinguish the88 source aliases from the3 reference-only additions."""
    aliases = identity.get('original_xmlids', [])
    index = {(row['module'], row['name']): row for row in aliases}
    require(len(index) == len(aliases), 'duplicate-original-alias')
    originals, reference = [], []
    for row in capsule['xmlids']:
        key = row['module'], row['name']
        if key in index:
            original = index[key]
            require(all(original.get(field) == row.get(field) for field in
                ('id', 'module', 'name', 'model', 'res_id', 'noupdate')), 'capsule-original-alias-drift')
            originals.append(original)
        else:
            reference.append(row)
    require(len(originals) == 88 and len(reference) == 3, 'source88-reference3-contract')
    report = index.get(('hr_payroll', 'action_report_payslip'))
    require(report and report['model'] == 'ir.actions.report' and type(report['res_id']) is int,
        'sealed-original-report-alias-required')
    return originals, reference, report


def expected_projection(rows):
    structures = {row['id'] for row in rows['hr_payroll_structure']}
    rules = rows['hr_salary_rule']
    require(len(structures) == 4 and len(rules) == 71, 'original4-structures71-rules-required')
    pairs = []
    for rule in rules:
        require(type(rule.get('struct_id')) is int and rule['struct_id'] in structures
            and type(rule.get('id')) is int and rule['id'] > 0, 'original-primary-owner-required')
        pairs.append((rule['struct_id'], rule['id']))
    require(len({rule for structure, rule in pairs}) == 71, 'original-rule-identity-ambiguous')
    return sorted(pairs)


def report_contract(identity, alias):
    source = identity.get('original_report_462')
    require(isinstance(source, dict) and source.get('table') == 'ir_act_report_xml',
        'full-original-report-baseline-required')
    columns, raw = source.get('columns'), source.get('rows_json')
    require(isinstance(columns, list) and columns and len(columns) == len(set(columns))
        and all(isinstance(name, str) and re.fullmatch(r'[a-z_][a-z0-9_]*', name) for name in columns),
        'original-report-column-contract')
    require(isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], str),
        'single-original-report-row-required')
    row = json.loads(raw[0])
    require(set(row) == set(columns) and row.get('id') == alias['res_id']
        and row.get('model') == 'hr.payslip' and row.get('type') == 'ir.actions.report'
        and row.get('report_type') == 'qweb-pdf', 'original-report-physical-identity')
    return source, row


def sql_tokens(code):
    """Ignore literals/comments, keep quoted identifiers, reject multi-statements.

    No SQL is evaluated here. This guard observes the real cursor and refuses
    history access or writes outside the actual projection call.
    """
    out, index = [], 0
    while index < len(code):
        char = code[index]
        if code.startswith('--', index):
            end = code.find('\n', index)
            index = len(code) if end < 0 else end + 1
            out.append(' ')
        elif code.startswith('/*', index):
            end = code.find('*/', index + 2)
            require(end >= 0 and '/*' not in code[index + 2:end], 'unreviewed-sql-comment')
            index = end + 2
            out.append(' ')
        elif char == "'":
            index += 1
            while index < len(code):
                if code[index] == "'":
                    index += 1
                    if index < len(code) and code[index] == "'":
                        index += 1
                        continue
                    break
                # Conservative refusal of backslash-escaped SQL literals.
                require(code[index] != '\\', 'unreviewed-sql-escape')
                index += 1
            else:
                raise ProbeBlocked('unterminated-sql-literal')
            out.append(' ')
        elif char == '"':
            end = code.find('"', index + 1)
            require(end > index + 1 and re.fullmatch(r'[A-Za-z0-9_]+', code[index + 1:end]),
                'unreviewed-sql-quoted-identifier')
            out.append(code[index + 1:end])
            index = end + 1
        else:
            require(char not in ';$', 'unreviewed-sql-multistatement-or-dollar-body')
            out.append(char)
            index += 1
    return re.findall(r'[a-z_][a-z0-9_]*|\S', ''.join(out).lower())


def admit_sql(code, *, projection=False):
    tokens = sql_tokens(code)
    require(tokens and not (set(tokens) & {'nextval', 'setval', 'set_config', 'dblink', 'lo_import', 'lo_export'}),
        'counter-or-session-or-external-operation-forbidden')
    require(not (set(tokens) & HISTORY_TABLES), 'payroll-history-or-account-read-forbidden')
    command = tokens[0]
    if command == 'insert':
        require(projection and len(tokens) > 7 and tokens[1:3] == ['into', 'hr_structure_salary_rule_rel']
            and tokens[3:8] == ['(', 'struct_id', ',', 'rule_id', ')']
            and 'unnest' in tokens and tokens[-4:] == ['on', 'conflict', 'do', 'nothing'],
            'only-real-projection-insert-permitted')
        # No writable CTE, RETURNING, trigger control, other table or chained SQL.
        require(not (set(tokens) & {'update', 'delete', 'returning', 'alter', 'create', 'drop', 'truncate'}),
            'projection-insert-shape-not-admitted')
    elif command == 'lock':
        require(projection and tokens == ['lock', 'table', 'hr_structure_salary_rule_rel', 'in',
            'share', 'row', 'exclusive', 'mode', 'nowait'], 'only-projection-lock-permitted')
    else:
        require(command in ('select', 'show', 'savepoint', 'release', 'rollback'),
            'non-projection-database-write-forbidden')
        lock_select = (projection and command == 'select' and tokens[-3:] == ['for', 'update', 'nowait']
            and tokens[:3] == ['select', 'id', 'from'] and tokens[3] in ('hr_payroll_structure', 'hr_salary_rule')
            and tokens.count('update') == 1)
        forbidden = {'insert', 'delete', 'create', 'alter', 'drop', 'truncate',
            'grant', 'revoke', 'call', 'copy', 'do', 'commit'}
        if not lock_select:
            forbidden.add('update')
        require(not (set(tokens) & forbidden), 'write-through-read-command-forbidden')
        if command == 'rollback':
            require(tokens[1:2] == ['to'], 'transaction-control-owned-by-coordinator')
    return command


@contextmanager
def observe_cursor(cr):
    """Delegate unchanged real SQL; no fake result or permission bypass."""
    cls, execute = type(cr), type(cr).execute
    observation = {'projection': False, 'statements': 0, 'inserts': 0,
        'historical_tables_read': False, 'counter_operations': False}

    def observed(cursor, query, *args, **kwargs):
        require(cursor is cr, 'additional-cursor-not-admitted')
        code = query if isinstance(query, str) else getattr(query, 'code', None)
        if code is None and hasattr(query, 'as_string'):
            code = query.as_string(cursor._cnx)
        require(isinstance(code, str), 'unreviewed-sql-object')
        command = admit_sql(code, projection=observation['projection'])
        observation['statements'] += 1
        observation['inserts'] += int(command == 'insert')
        return execute(cursor, query, *args, **kwargs)

    cls.execute = observed
    try:
        yield observation
    finally:
        cls.execute = execute


def project_rows(cr, table, columns, ids=None):
    require(columns and len(columns) == len(set(columns)), 'projection-columns-required')
    for name in columns:
        identifier(name)
    query = ('SELECT (SELECT jsonb_object_agg(k,v) FROM jsonb_each(to_jsonb(t)) AS j(k,v) '
        'WHERE k=ANY(%s))::text FROM public.' + identifier(table) + ' t')
    params = [columns]
    if ids is not None:
        query += ' WHERE t.id=ANY(%s)'
        params.append(ids)
    query += ' ORDER BY t.id' if ids is not None else ' ORDER BY to_jsonb(t)::text'
    cr.execute(query, params)
    return [row[0] for row in cr.fetchall()]


def masters_contract(cr, capsule, rows):
    result = {}
    for table, source in capsule['tables'].items():
        columns = [row['name'] for row in source['columns']]
        cr.execute('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass '
            'AND attnum>0 AND NOT attisdropped ORDER BY attnum', ['public.' + table])
        require(set(columns) <= {row[0] for row in cr.fetchall()}, 'original-physical-column-missing')
        ids = [row['id'] for row in rows[table]] if table in rows else None
        actual = project_rows(cr, table, columns, ids)
        require(actual == source['rows_json'], 'original-master-column-projection-drift')
        result[table] = {'rows': len(actual), 'columns': len(columns), 'rows_sha256': sha('\n'.join(actual).encode())}
    return result


def actual_aliases(cr, aliases):
    result = []
    for source in sorted(aliases, key=lambda row: row['id']):
        columns = sorted(source)
        raw = project_rows(cr, 'ir_model_data', columns, [source['id']])
        require(len(raw) == 1 and json.loads(raw[0]) == source, 'original-alias-column-drift')
        result.append({'id': source['id'], 'model': source['model'], 'res_id': source['res_id'],
            'columns': columns, 'row_sha256': sha(raw[0].encode())})
    return result


def master_audit(cr):
    result = {}
    for table in gate.TABLES:
        cr.execute('SELECT to_jsonb(t)::text FROM public.' + identifier(table) + ' t ORDER BY id')
        raw = [row[0] for row in cr.fetchall()]
        result[table] = {'rows': len(raw), 'all_current_columns_sha256': sha('\n'.join(raw).encode())}
    return result


def counters(cr):
    result = {}
    for table in ('ir_sequence', 'ir_sequence_date_range'):
        cr.execute('SELECT to_jsonb(t)::text FROM public.' + identifier(table) + ' t ORDER BY id')
        result[table] = sha('\n'.join(row[0] for row in cr.fetchall()).encode())
    cr.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='S' AND c.relname ~ '^ir_sequence_[0-9]+(_[0-9]+)?$' ORDER BY c.relname")
    names = [row[0] for row in cr.fetchall()]
    for name in names:
        cr.execute('SELECT last_value,is_called FROM public.' + identifier(name))
        result[name] = list(cr.fetchone())
    return result


def engine_contract(env, identity):
    cr = env.cr
    cr.execute("SELECT name,license,state FROM ir_module_module WHERE state='installed' OR "
        "name IN ('payroll','payroll_account','hr_payroll','hr_payroll_account') ORDER BY name")
    modules = cr.fetchall()
    require(not any(license == 'OEEL-1' and state == 'installed' for name, license, state in modules),
        'installed-enterprise-modules-remain')
    require({name for name, license, state in modules if state == 'installed' and name in
        ('payroll', 'payroll_account', 'hr_payroll', 'hr_payroll_account')} == {'payroll', 'payroll_account'},
        'only-real-oca-payroll-providers-required')
    require(all(license == 'LGPL-3' for name, license, state in modules
        if name in ('payroll', 'payroll_account') and state == 'installed'), 'oca-provider-license-contract')
    cr.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
    require(cr.fetchone()[0] == 0, 'pending-module-operations')
    payslip = env['hr.payslip']
    mro = [cls.__module__ + '.' + cls.__name__ for cls in type(payslip).__mro__]
    require(payslip._table == 'hr_payslip' and payslip._auto is True and not payslip._abstract
        and not payslip._transient and any(name.startswith('odoo.addons.payroll.models.') for name in mro)
        and not any(re.match(r'odoo\.addons\.hr_payroll(?:_account)?\.', name) for name in mro),
        'actual-oca-mro-required-no-native-payroll-class')
    model_rows = [row for row in identity['ir_model'] if row.get('model') == 'hr.payslip']
    require(len(model_rows) == 1 and type(model_rows[0]['id']) is int, 'sealed-payslip-model-identity-required')
    cr.execute('SELECT id,model FROM ir_model WHERE id=%s OR model=%s ORDER BY id',
        [model_rows[0]['id'], 'hr.payslip'])
    require(cr.fetchall() == [(model_rows[0]['id'], 'hr.payslip')], 'original-payslip-model-id-drift')
    return {'installed': sum(state == 'installed' for name, license, state in modules), 'enterprise': 0,
        'providers': ['payroll', 'payroll_account'], 'mro': mro, 'original_model_id': model_rows[0]['id'],
        'model_identity_scope': ['id', 'model'], 'real_oca_engine': True}


def existing_manager(env, identity, source_rows, actor_uid):
    from odoo import api

    aliases = {(row['module'], row['name']): row for row in identity['original_xmlids']}
    manager = aliases.get(('hr_payroll', 'group_hr_payroll_manager'))
    require(manager and manager['model'] == 'res.groups', 'original-manager-role-required')
    actual_aliases(env.cr, [manager])
    membership = env['res.users']._fields['groups_id']
    require(membership.type == 'many2many' and membership.comodel_name == 'res.groups',
        'real-user-group-membership-binding-required')
    sql = ('SELECT u.id FROM res_users u JOIN ' + identifier(membership.relation) + ' g ON g.'
        + identifier(membership.column1) + '=u.id WHERE g.' + identifier(membership.column2)
        + '=%s AND u.active AND NOT u.share AND u.id<>1 ORDER BY u.id')
    env.cr.execute(sql, [manager['res_id']])
    candidates = [row[0] for row in env.cr.fetchall()]
    require(candidates and (actor_uid is None or type(actor_uid) is int and actor_uid in candidates),
        'existing-normal-legacy-manager-required')
    # Deterministic selection, preferring a genuine non-system manager. A
    # coordinator may name an existing legacy manager but cannot grant one.
    if actor_uid is None:
        regular = [uid for uid in candidates if not env['res.users'].browse(uid).has_group('base.group_system')]
        actor_uid = (regular or candidates)[0]
    user = env['res.users'].browse(actor_uid)
    companies = user.company_ids
    allowed = companies.ids
    require(allowed and user.company_id.id in allowed, 'existing-company-membership-required')
    countries = {row.get('country_id') for row in source_rows['hr_payroll_structure'] if row.get('country_id')}
    compatible = companies.filtered(lambda company: not countries or company.country_id.id in countries)
    require(compatible, 'legacy-manager-has-no-compatible-original-country-company')
    company = user.company_id if user.company_id in compatible else compatible.sorted('id')[0]
    selected = [company.id] + sorted(set(allowed) - {company.id})
    scope = api.Environment(env.cr, actor_uid, {'allowed_company_ids': selected,
        'active_test': False, 'lang': user.lang or 'en_US'}, su=False)
    require(not scope.su and scope.uid != 1 and scope.company.id == company.id
        and set(scope.user.company_ids.ids) == set(allowed), 'normal-actor-company-boundary')
    require(scope.user.has_group('hr_payroll.group_hr_payroll_manager')
        and scope.user.has_group('base.group_user'), 'legacy-normal-internal-manager-required')
    return scope, {'uid': actor_uid, 'legacy_manager_group_id': manager['res_id'],
        'allowed_company_ids': sorted(allowed), 'active_company_id': company.id,
        'superuser': False, 'system_group_member': user.has_group('base.group_system'),
        'users_created': False, 'permissions_granted': False, 'company_memberships_changed': False}


def forms_and_menus(scope):
    from lxml import etree
    from odoo.tools import json_default

    forms = {}
    for model, alias in FORMS:
        view = scope.ref(alias, raise_if_not_found=False)
        require(view and view._name == 'ir.ui.view' and view.model == model and view.type == 'form'
            and not view.inherit_id, 'explicit-community-primary-form-required:' + model)
        scope[model].check_access('read')
        value = scope[model].get_view(view_id=view.id, view_type='form')
        require(etree.fromstring(value['arch'].encode()).tag == 'form', 'actual-form-architecture-required')
        json.dumps(value, default=json_default)
        forms[model] = {'alias': alias, 'view_id': view.id, 'arch_sha256': sha(value['arch'].encode()),
            'normal_actor': True, 'record_created': False}
    visible = scope['ir.ui.menu']._visible_menu_ids(debug=False)
    root = scope.ref('payroll.payroll_menu_root', raise_if_not_found=False)
    require(root and root.id in visible, 'oca-payroll-root-not-visible-to-existing-actor')
    menus = []
    for menu_alias, action_alias, model in MENUS:
        menu = scope.ref(menu_alias, raise_if_not_found=False)
        require(menu and menu.id in visible, 'community-configuration-menu-not-visible:' + model)
        action = scope['ir.actions.actions']._for_xml_id(action_alias)
        require(action.get('res_model') == model and 'form' in action.get('view_mode', '').split(','),
            'community-menu-action-form-contract:' + model)
        json.dumps(action, default=json_default)
        menus.append({'menu_id': menu.id, 'action_id': action['id'], 'model': model,
            'normal_actor_visible': True, 'resolved_by_actual_action_api': True})
    return forms, menus


def legacy_menu_boundaries(scope, identity):
    """No action is executed, domain evaluated or legacy application certified."""
    source = {row['id']: row for row in identity.get('ir_ui_menu', [])}
    aliases = [row for row in identity['original_xmlids'] if row['model'] == 'ir.ui.menu'
        and row['module'] in ('hr_payroll', 'hr_payroll_account', 'l10n_cl_simpledigital_payroll')]
    visible = scope['ir.ui.menu']._visible_menu_ids(debug=False)
    results = []
    for alias in aliases:
        original = source.get(alias['res_id'])
        require(original, 'original-legacy-menu-metadata-missing')
        action = original.get('action')
        entry = {'menu_id': alias['res_id'], 'original_metadata_sha256': digest(original),
            'visible': alias['res_id'] in visible, 'action_executed': False,
            'full_flow_certified': False, 'blocker': 'legacy-action-flow-not-exercised'}
        if isinstance(action, str) and re.fullmatch(r'ir\.actions\.act_window,[0-9]+', action):
            action_id = int(action.split(',')[1])
            scope.cr.execute('SELECT res_model FROM ir_act_window WHERE id=%s', [action_id])
            row = scope.cr.fetchone()
            entry.update(action_id=action_id, target_model_exists=bool(row and row[0] in scope.registry))
            if not row or row[0] not in scope.registry:
                entry['blocker'] = 'legacy-action-model-unavailable'
        results.append(entry)
    return results


def report_route(scope, source_row):
    report_id = source_row['id']
    report = scope['ir.actions.report'].browse(report_id)
    report.check_access('read')
    require(report.exists().ids == [report_id], 'original-report-not-readable-by-existing-manager')
    route = source_row.get('report_name')
    require(isinstance(route, str) and re.fullmatch(r'[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_.]*', route),
        'original-report-renderer-name-contract')
    resolver = getattr(report, '_step_original_report_target', None)
    require(callable(resolver), 'actual-original-community-report-route-required')
    target = resolver(report_id)  # Real configuration lookup; no document is supplied.
    require(isinstance(target, tuple) and len(target) == 3 and target[0].env.uid == scope.uid
        and not target[0].env.su and target[1].ids == [report_id]
        and target[2]._name == 'report.step_simpledigital_oca_base.report_payslip'
        and target[2]._original_module == 'step_simpledigital_oca_base'
        and target[2].env.uid == scope.uid and not target[2].env.su,
        'real-stored-community-renderer-must-retain-actor')
    template = scope.ref('step_simpledigital_oca_base.report_payslip', raise_if_not_found=False)
    qweb = bool(template and template._name == 'ir.ui.view' and template.type == 'qweb' and template.active)
    renderer = callable(getattr(report, '_render_qweb_pdf', None))
    require(renderer and qweb and callable(getattr(target[2], '_get_report_values', None)),
        'original-report-renderer-route-unavailable')
    return {'id': report_id, 'report_name': route, 'qweb_template_metadata_exists': qweb,
        'community_stored_renderer': target[2]._name, 'actual_pdf_renderer_callable': renderer,
        'normal_actor_can_read_action': True, 'pdf_rendered': False,
        'payslips_read': False, 'financial_or_legal_certification': False}


def pairs_now(cr, structures, rules):
    cr.execute('SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel '
        'WHERE struct_id=ANY(%s) OR rule_id=ANY(%s) ORDER BY struct_id,rule_id', [structures, rules])
    return [list(row) for row in cr.fetchall()]


def write_receipt(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def run(env, capsule_path, capsule_sha256, identity_before_path, identity_sha256, output_path, actor_uid=None):
    """No commit: the caller owns the clone, lease, outer transaction and seal.

    On any rejection, the private receipt has ``passed=False`` and the real
    savepoint is rolled back. Exceptions contain technical codes only.
    """
    require(re.fullmatch(DATABASE, env.cr.dbname or ''), 'private-original-handover-database-required')
    require(capsule_sha256 == CAPSULE_SHA256, 'unreviewed-original-capsule')
    output = Path(output_path)
    require(output.is_absolute() and output.resolve().is_relative_to(PRIVATE_ROOT)
        and output.parent.is_dir() and not output.exists() and not output.is_symlink(),
        'new-private-output-required')
    result = {'schema': 1, 'database': env.cr.dbname, 'probe_sha256': sha(Path(__file__).read_bytes()),
        'capsule_sha256': capsule_sha256, 'identity_before_sha256': identity_sha256,
        'passed': False, 'coordinator_owns_commit': True, 'historical_payroll_read': False,
        'salary_rules_evaluated': False, 'financial_certified': False, 'pdf_certified': False,
        'operational_package': False, 'integral_conversion': False, 'deadline_resolved': False}
    try:
        capsule = sealed_json(capsule_path, capsule_sha256)
        identity = sealed_json(identity_before_path, identity_sha256)
        rows = gate.capsule_rows(capsule)
        require(sum(len(value) for value in rows.values()) == 120, 'original120-master-cohort-required')
        expected = expected_projection(rows)
        originals, reference, report_alias = source_alias_contract(capsule, identity)
        source_report, report_row = report_contract(identity, report_alias)
        aliases = originals + [report_alias]
        with env.cr.savepoint(flush=False):
            with observe_cursor(env.cr) as observation:
                from run_original_anchor_loader import check_database_guards
                result['database_guards'] = check_database_guards(env.cr)
                result['engine'] = engine_contract(env, identity)
                require(report_row.get('binding_model_id') == result['engine']['original_model_id'],
                    'original-report-payslip-model-binding-drift')
                before = masters_contract(env.cr, capsule, rows)
                alias_before = actual_aliases(env.cr, aliases)
                report_before = project_rows(env.cr, 'ir_act_report_xml', source_report['columns'], [report_row['id']])
                require(report_before == source_report['rows_json'], 'full-original-report-row-drift')
                audit_before, counter_before = master_audit(env.cr), counters(env.cr)
                scope, actor = existing_manager(env, identity, rows, actor_uid)
                result['actor'] = actor
                for table, model in gate.TABLES.items():
                    records = scope[model].browse(sorted(row['id'] for row in rows[table]))
                    records.check_access('read')
                    require(set(records.exists().ids) == set(records.ids), 'original-master-not-visible:' + model)
                result['forms'], result['menus'] = forms_and_menus(scope)
                result['legacy_menu_boundaries'] = legacy_menu_boundaries(scope, identity)
                result['report_route'] = report_route(scope, report_row)
                structures = scope['hr.payroll.structure'].browse(sorted(row['id'] for row in rows['hr_payroll_structure']))
                require(callable(getattr(structures, '_step_materialize_original_rule_projection', None)),
                    'real-original-projection-api-missing')
                env.cr.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid="
                    "'hr_structure_salary_rule_rel'::regclass AND NOT tgisinternal")
                require(env.cr.fetchone()[0] == 0, 'unreviewed-projection-relation-trigger')
                projection_before = pairs_now(env.cr, structures.ids, [rule for structure, rule in expected])
                require(set(map(tuple, projection_before)) <= set(expected), 'unexpected-preexisting-rule-membership')
                observations = []
                for index in range(2):
                    observation['projection'] = True
                    try:
                        proof = structures._step_materialize_original_rule_projection([list(pair) for pair in expected])
                    finally:
                        observation['projection'] = False
                    require(proof.get('projection_equivalent') is True and proof.get('memberships') == 71
                        and proof.get('pairs') == [list(pair) for pair in expected]
                        and proof.get('master_rows_written') is False and proof.get('payroll_read_or_recomputed') is False
                        and proof.get('financial_certified') is False, 'actual-projection-api-result-not-equivalent')
                    require(proof.get('created_memberships') == (len(expected) - len(projection_before) if index == 0 else 0),
                        'actual-projection-created-count-or-idempotence')
                    require(pairs_now(env.cr, structures.ids, [rule for structure, rule in expected])
                        == [list(pair) for pair in expected], 'actual71-memberships-not-exact')
                    require(master_audit(env.cr) == audit_before, 'master-or-audit-fields-written-by-projection')
                    observations.append(proof)
                require(masters_contract(env.cr, capsule, rows) == before, 'original-master-projection-changed')
                require(actual_aliases(env.cr, aliases) == alias_before, 'original-aliases-changed')
                report_after = project_rows(env.cr, 'ir_act_report_xml', source_report['columns'], [report_row['id']])
                require(report_after == report_before, 'original-report-changed')
                require(counters(env.cr) == counter_before, 'business-counter-changed')
                result.update(passed=True, original_master_count=120, original_rule_count=71,
                    source_original_aliases=88, reference_only_aliases_not_adopted=len(reference),
                    original_aliases_and_report_alias=alias_before, master_original_columns=before,
                    master_all_current_columns_and_audit=audit_before,
                    original_report={'id': report_row['id'], 'columns': source_report['columns'],
                        'raw_sha256': sha(report_before[0].encode()), 'all_source_columns_exact': True},
                    original_rule_projection=observations, projection_initial_memberships=len(projection_before),
                    original_rule_projection_idempotent=True, only_projection_memberships_written=True,
                    source_master_and_audit_fields_exact=True, business_counters_exact=True,
                    counter_contract_sha256=digest(counter_before), original_alias_columns_exact=True,
                    sql_observation={key: value for key, value in observation.items() if key != 'projection'},
                    all_legacy_flows_certified=False, masters_imported=False, source_identity_preserved=True,
                    original_metadata_semantics_admitted=False, opaque_reference_semantics_admitted=False,
                    remaining_adoption_blockers=['original-field-metadata-requires-separate-admission',
                        'opaque-reference-semantics-not-certified', 'legacy-menu-flows-not-exercised',
                        'salary-financial-certification-pending', 'integral-enterprise-conversion-pending'])
        write_receipt(output, result)
        return result
    except Exception as error:
        code = str(error) if isinstance(error, ProbeBlocked) else 'actual-api-or-guard-rejected:' + type(error).__name__
        result.update(passed=False, blocked=code, projection_transaction_rolled_back=True)
        write_receipt(output, result)
        raise ProbeBlocked(code) from None
