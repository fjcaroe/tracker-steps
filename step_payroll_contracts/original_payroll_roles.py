"""Read-only policy contract for two new OCA aliases to existing native roles.

The migration writer inserts aliases. This helper never creates/updates a
group, membership, implied edge, ACL or rule. Common-model policy must remain
literal; OCA-only empty models have a separate, deliberately read-only profile.
"""
from dataclasses import asdict, dataclass

from psycopg2 import sql

from .original_benefit_cohort import _environment, require


ALIASES = (('group_hr_payroll_user', 'group_payroll_user'),
    ('group_hr_payroll_manager', 'group_payroll_manager'))
COMMON_MODELS = ('hr.contract', 'hr.employee', 'hr.payroll.structure', 'hr.payroll.structure.type',
    'hr.salary.rule', 'hr.salary.rule.category', 'hr.payslip', 'hr.payslip.line', 'hr.payslip.input',
    'hr.payslip.input.type', 'hr.payslip.worked_days', 'hr.payslip.run', 'hr.payslip.employees')
OCA_ONLY_MODELS = ('hr.contribution.register', 'hr.rule.input')
OCA_UNGRANTED_TRANSIENTS = ('hr.payslip.change.state', 'payslip.lines.contribution.register')


@dataclass(frozen=True)
class PayrollRoleBindingPlan:
    database: str
    original_alias_rows: tuple
    original_model_rows: tuple
    original_field_ids: tuple
    policy_rows: tuple
    bindings: tuple

    def metadata(self):
        return dict(asdict(self), new_aliases_only=True, groups_written=False,
            implied_edges_written=False, memberships_written=False, common_model_grants_added=False,
            policy_domain_equivalence_inferred=False, functional_role_parity_certified=False)


def _hash(cr, table, where='', parameters=()):
    cr.execute(sql.SQL("SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,"
        "E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') FROM {} t ").format(sql.Identifier(table))
        + sql.SQL(where), parameters)
    count, digest = cr.fetchone()
    return table, count, digest


def _original_aliases(cr):
    cr.execute("SELECT id,module,name,model,res_id,noupdate FROM ir_model_data WHERE module='hr_payroll' "
        "AND name=ANY(%s) ORDER BY name", ([name for name, target in ALIASES],))
    rows = tuple(cr.fetchall())
    require(len(rows) == 2 and {row[3] for row in rows} == {'res.groups'}
        and len({row[4] for row in rows}) == 2, 'two-distinct-original-payroll-roles-required')
    cr.execute('SELECT id FROM res_groups WHERE id=ANY(%s) ORDER BY id', ([row[4] for row in rows],))
    require(len(cr.fetchall()) == 2, 'original-payroll-group-identity-missing')
    return rows


def _bindings(original):
    groups = {row[2]: row[4] for row in original}
    return tuple(('payroll', target, 'res.groups', groups[source], True) for source, target in ALIASES)


def _existing_new_aliases(cr, bindings, *, complete):
    cr.execute("SELECT module,name,model,res_id,noupdate FROM ir_model_data WHERE module='payroll' "
        "AND name=ANY(%s) ORDER BY name", ([row[1] for row in bindings],))
    rows = tuple(cr.fetchall())
    expected = {row[1]: row for row in bindings}
    require(all(row == expected[row[1]] for row in rows), 'oca-role-alias-collision-no-update-authorized')
    if complete:
        require(len(rows) == 2, 'both-new-oca-role-aliases-required')
    return rows


def _policy(cr, group_ids, model_rows, field_ids):
    model_ids = [row[0] for row in model_rows]
    # Full membership/implied tables make grants via another group visible.
    # This strict contract cannot silently bless new implication paths.
    return (
        _hash(cr, 'res_groups', 'WHERE t.id=ANY(%s)', (list(group_ids),)),
        _hash(cr, 'res_groups_users_rel'), _hash(cr, 'res_groups_implied_rel'),
        _hash(cr, 'ir_model_access', 'WHERE t.model_id=ANY(%s)', (model_ids,)),
        _hash(cr, 'ir_rule', 'WHERE t.model_id=ANY(%s)', (model_ids,)),
        _hash(cr, 'rule_group_rel', 'WHERE t.rule_group_id IN (SELECT id FROM ir_rule WHERE model_id=ANY(%s))', (model_ids,)),
        _hash(cr, 'ir_model_fields_group_rel', 'WHERE t.field_id=ANY(%s)', (list(field_ids),)),
    )


def plan_original_payroll_role_bindings(cr, *, expected_database):
    """Resolve existing identities and immutable policy, never infer membership."""
    _environment(cr, expected_database)
    cr.execute("SELECT count(*) FROM ir_module_module WHERE name='hr_payroll' AND license='OEEL-1' AND state='installed'")
    require(cr.fetchone() == (1,), 'original-native-role-source-required')
    cr.execute('SELECT model FROM ir_model WHERE model=ANY(%s)', (list(OCA_ONLY_MODELS + OCA_UNGRANTED_TRANSIENTS),))
    require(not cr.fetchall(), 'oca-only-source-models-need-separate-preservation-admission')
    original = _original_aliases(cr)
    bindings = _bindings(original)
    _existing_new_aliases(cr, bindings, complete=False)
    cr.execute('SELECT id,model FROM ir_model WHERE model=ANY(%s) ORDER BY model', (list(COMMON_MODELS),))
    models = tuple(cr.fetchall())
    require({'hr.payslip', 'hr.salary.rule', 'hr.payroll.structure'} <= {row[1] for row in models},
        'original-common-payroll-models-required')
    cr.execute('SELECT id FROM ir_model_fields WHERE model=ANY(%s) ORDER BY id', (list(COMMON_MODELS),))
    fields = tuple(row[0] for row in cr.fetchall())
    return PayrollRoleBindingPlan(expected_database, original, models, fields,
        _policy(cr, [row[4] for row in original], models, fields), bindings)


def verify_original_payroll_role_bindings(cr, plan, *, expected_database):
    """Verify the writer's two aliases and exact source policy after handover."""
    require(type(plan) is PayrollRoleBindingPlan, 'actual-original-role-plan-required')
    _environment(cr, expected_database)
    require(_original_aliases(cr) == plan.original_alias_rows, 'original-role-aliases-changed')
    cr.execute('SELECT id,model FROM ir_model WHERE model=ANY(%s) ORDER BY model', (list(COMMON_MODELS),))
    require(tuple(cr.fetchall()) == plan.original_model_rows, 'original-common-model-identities-changed')
    require(_policy(cr, [row[4] for row in plan.original_alias_rows], plan.original_model_rows,
        plan.original_field_ids) == plan.policy_rows, 'original-group-or-common-model-policy-changed')
    _existing_new_aliases(cr, plan.bindings, complete=True)
    return dict(bindings=[list(row) for row in plan.bindings], original_aliases_preserved=True,
        original_groups_preserved=True, implied_edges_preserved=True, memberships_preserved=True,
        original_common_policy_exact=True, new_aliases_only=True,
        common_model_grants_added=False, functional_role_parity_certified=False)


def admit_empty_oca_models_readonly_manager(env, *, manager_group_id):
    """Separate target profile: actual upstream models, no rows and no CRUD."""
    require(type(manager_group_id) is int and manager_group_id > 0, 'explicit-original-manager-id-required')
    reports = []
    for name in OCA_ONLY_MODELS:
        model = env.registry.models.get(name)
        require(model is not None and any(klass.__module__.startswith('odoo.addons.payroll.models.')
            for klass in model.__mro__), 'actual-oca-only-model-required')
        table = model._table  # Real registry binding, never model-name replacement.
        env.cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
        require(env.cr.fetchone() == (0,), 'oca-only-model-must-be-empty')
        env.cr.execute('SELECT id FROM ir_model WHERE model=%s', (name,))
        row = env.cr.fetchone()
        require(row is not None, 'actual-oca-only-model-identity-required')
        env.cr.execute('SELECT group_id,perm_read,perm_write,perm_create,perm_unlink FROM ir_model_access '
            'WHERE model_id=%s AND active ORDER BY id', (row[0],))
        acl = env.cr.fetchall()
        require(bool(acl) and all(group == manager_group_id and read and not any((write, create, unlink))
            for group, read, write, create, unlink in acl), 'oca-only-readonly-manager-policy-required')
        reports.append({'model': name, 'table': table, 'rows': 0, 'readonly_manager_only': True})
    transients = []
    for name in OCA_UNGRANTED_TRANSIENTS:
        model = env.registry.models.get(name)
        require(model is not None and model._transient and any(klass.__module__.startswith('odoo.addons.payroll.wizard.')
            for klass in model.__mro__), 'actual-oca-only-transient-required')
        env.cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(model._table)))
        require(env.cr.fetchone() == (0,), 'oca-only-transient-must-be-empty')
        env.cr.execute('SELECT count(*) FROM ir_model_access WHERE active AND model_id IN '
            '(SELECT id FROM ir_model WHERE model=%s)', (name,))
        require(env.cr.fetchone() == (0,), 'oca-only-transient-must-have-no-new-grants')
        transients.append({'model': name, 'table': model._table, 'rows': 0, 'operational': False})
    return dict(models=reports, ungranted_transients=transients,
        configuration_crud_enabled=False, original_common_policy_changed=False,
        financial_certified=False, functional_role_parity_certified=False)
