"""Data-only admission of an anchored configuration cohort, never a benefit API.

The native family stays in its original 14 tables and retains its original
identities. Empty inverse membership can unblock the five configuration tables;
it does not implement salary packages, offers, summaries or salary_benefits_ids.
Only a privileged migration coordinator calls this SQL/registry-metadata API.
No business record, formula, credential, callable or Enterprise body is read.
"""
from dataclasses import asdict, dataclass

from psycopg2 import sql


FAMILY_TABLES = (
    'hr_contract_salary_benefit', 'hr_contract_salary_benefit_hr_contract_salary_resume_rel',
    'hr_contract_salary_benefit_ir_model_fields_rel', 'hr_contract_salary_benefit_rel',
    'hr_contract_salary_benefit_type', 'hr_contract_salary_benefit_value', 'hr_contract_salary_offer',
    'hr_contract_salary_offer_refusal_reason', 'hr_contract_salary_offer_sign_request_rel',
    'hr_contract_salary_personal_info', 'hr_contract_salary_personal_info_type',
    'hr_contract_salary_personal_info_value', 'hr_contract_salary_resume', 'hr_contract_salary_resume_category',
)
COHORT_TABLES = ('hr_payroll_structure_type', 'hr_payroll_structure', 'hr_salary_rule',
    'hr_salary_rule_category', 'hr_payslip_input_type')
FRONTIERS = (
    ('hr_contract_salary_benefit', 'structure_type_id', 'r'),
    ('hr_contract_salary_personal_info', 'structure_type_id', 'n'),
    ('hr_contract_salary_resume', 'structure_type_id', 'n'),
)


class BenefitCohortError(ValueError):
    pass


def require(value, code):
    if not value:
        raise BenefitCohortError('original-benefit-cohort-' + code)


@dataclass(frozen=True)
class BenefitCohortSource:
    database: str
    type_ids: tuple
    field_rows: tuple
    family_rows: tuple
    inbound_rows: tuple
    transaction_read_only: bool

    def metadata(self):
        memberships = sum(row[1] for row in self.inbound_rows[0][2])
        return dict(asdict(self), source_rows=sum(row[1] for row in self.family_rows),
            cohort_benefit_memberships=memberships, configuration_data_only=True,
            salary_benefits_ids_implemented=False, native_benefit_engine_implemented=False,
            original_identity_adopted=False, financial_certified=False, integral_conversion=False)


def _environment(cr, expected_database):
    require(isinstance(expected_database, str) and bool(expected_database), 'explicit-database-required')
    cr.execute("SELECT current_database(),current_setting('transaction_read_only'),current_setting('transaction_isolation')")
    database, read_only, isolation = cr.fetchone()
    require(database == expected_database, 'database-differs')
    require(isolation in ('repeatable read', 'serializable'), 'stable-snapshot-required')
    return read_only == 'on'


def _ids(type_ids):
    require(isinstance(type_ids, (tuple, list)) and bool(type_ids)
        and all(type(value) is int and 0 < value < 2**31 for value in type_ids)
        and len(type_ids) == len(set(type_ids)), 'explicit-existing-type-identities-required')
    return tuple(sorted(type_ids))


def _family_snapshot(cr):
    cr.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relname ~ '^hr_contract_salary_' ORDER BY c.relname")
    require(tuple(row[0] for row in cr.fetchall()) == FAMILY_TABLES, 'exact-native-family-required')
    result = []
    for table in FAMILY_TABLES:
        cr.execute(sql.SQL("SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text,"
            "E'\\n' ORDER BY to_jsonb(t)::text),''),'UTF8')),'hex') FROM {} t").format(sql.Identifier(table)))
        count, digest = cr.fetchone()
        result.append((table, count, digest))
    return tuple(result)


def _native_field_rows(cr):
    cr.execute("""SELECT id,model,name,ttype,relation,relation_field,store,required,readonly,related,on_delete
        FROM ir_model_fields WHERE (model='hr.payroll.structure.type' AND name='salary_benefits_ids')
        OR (model='hr.contract.salary.benefit' AND name='structure_type_id') ORDER BY model,name""")
    rows = tuple(cr.fetchall())
    require(len(rows) == 2, 'original-field-identities-required')
    require(rows[0][1:] == ('hr.contract.salary.benefit', 'structure_type_id', 'many2one',
        'hr.payroll.structure.type', None, True, True, False, None, 'restrict'), 'original-inverse-contract-differs')
    require(rows[1][1:] == ('hr.payroll.structure.type', 'salary_benefits_ids', 'one2many',
        'hr.contract.salary.benefit', 'structure_type_id', True, False, False, None, None), 'original-o2m-contract-differs')
    cr.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='hr_payroll_structure_type' AND column_name='salary_benefits_ids'")
    require(cr.fetchone() == (0,), 'o2m-must-not-be-a-shadow-column')
    return rows


def _inbound(cr, type_ids):
    # These are physical native bindings, not model.replace('.', '_') guesses.
    cr.execute("""SELECT sc.relname,
        ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(n,o)
            JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.n ORDER BY k.o),
        tc.relname,
        ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(n,o)
            JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.n ORDER BY k.o),
        c.confdeltype,c.convalidated
        FROM pg_constraint c JOIN pg_class sc ON sc.oid=c.conrelid
        JOIN pg_namespace sn ON sn.oid=sc.relnamespace JOIN pg_class tc ON tc.oid=c.confrelid
        JOIN pg_namespace tn ON tn.oid=tc.relnamespace WHERE c.contype='f'
        AND sn.nspname='public' AND tn.nspname='public' AND sc.relname=ANY(%s) AND tc.relname=ANY(%s)
        ORDER BY sc.relname,c.conname""", (list(FAMILY_TABLES), list(COHORT_TABLES)))
    actual = tuple((table, tuple(columns), target, tuple(target_columns), delete, valid)
        for table, columns, target, target_columns, delete, valid in cr.fetchall())
    expected = tuple((table, (column,), 'hr_payroll_structure_type', ('id',), delete, True)
        for table, column, delete in FRONTIERS)
    require(actual == expected, 'native-family-cohort-foreign-key-frontier-differs')
    result = []
    for table, column, delete in FRONTIERS:
        cr.execute(sql.SQL("SELECT {},count(*),encode(sha256(convert_to(string_agg(id::text,E'\\n' ORDER BY id),'UTF8')),'hex') "
            "FROM {} WHERE {}=ANY(%s) GROUP BY {} ORDER BY {}").format(sql.Identifier(column), sql.Identifier(table),
            sql.Identifier(column), sql.Identifier(column), sql.Identifier(column)), (list(type_ids),))
        result.append((table, column, tuple(cr.fetchall())))
    return tuple(result)


def _source_facts(cr, type_ids, *, expected_database):
    """Internal SQL observation also exercised on real native test fixtures."""
    read_only = _environment(cr, expected_database)
    identities = _ids(type_ids)
    before = _family_snapshot(cr)
    fields = _native_field_rows(cr)
    cr.execute('SELECT id FROM hr_payroll_structure_type WHERE id=ANY(%s) ORDER BY id', (list(identities),))
    require(tuple(row[0] for row in cr.fetchall()) == identities, 'original-type-identity-missing')
    inbound = _inbound(cr, identities)
    after = _family_snapshot(cr)
    require(before == after, 'native-family-changed-during-observation')
    return BenefitCohortSource(expected_database, identities, fields, before, inbound, read_only)


def _require_empty_membership(plan):
    require(not plan.inbound_rows[0][2], 'nonempty-original-benefit-membership')
    return plan


def admit_source_benefit_cohort(cr, type_ids, *, expected_database):
    """Read actual native storage; a serialized zero-count receipt is no input."""
    require(_environment(cr, expected_database), 'source-transaction-must-be-readonly')
    cr.execute("SELECT name,license FROM ir_module_module WHERE name='hr_contract_salary' AND state='installed'")
    require(cr.fetchall() == [('hr_contract_salary', 'OEEL-1')], 'native-source-provider-required')
    return _require_empty_membership(_source_facts(cr, type_ids, expected_database=expected_database))


def inspect_oca_benefit_boundary(env):
    """Actual registry class/field metadata only, with no data-admission grant."""
    payslip = env.registry.models.get('hr.payslip')
    require(payslip is not None and any(klass.__module__.startswith('odoo.addons.payroll.models.')
        for klass in payslip.__mro__), 'actual-oca-payslip-registry-required')
    require(not any(klass.__module__.startswith('odoo.addons.hr_payroll.models.')
        for klass in payslip.__mro__), 'native-payslip-backend-remains-loaded')
    kind = env.registry.models.get('hr.payroll.structure.type')
    require(kind is not None, 'actual-type-registry-required')
    require('salary_benefits_ids' not in kind._fields and not any(name.startswith('hr.contract.salary.')
        for name in env.registry.models), 'benefit-runtime-interface-must-remain-explicitly-unimplemented')
    return dict(actual_oca_payslip_registry=True, salary_benefits_ids_implemented=False,
        native_benefit_engine_implemented=False, configuration_data_cohort_admissible=False,
        integral_conversion=False)


def admit_target_benefit_cohort(env, source_plan, *, expected_database, mode):
    """Allow only the anchored data cohort, retaining all original family rows.

    The real OCA registry intentionally has no native benefit interface. No
    absent field, empty model, new alias or alternate benefit table is created.
    This permits neither an unanchored import nor an operational benefit flow.
    """
    require(mode == 'anchored-preserved', 'explicit-anchored-preserved-mode-required')
    require(type(source_plan) is BenefitCohortSource and source_plan.transaction_read_only,
        'actual-readonly-source-plan-required')
    _require_empty_membership(source_plan)
    _environment(env.cr, expected_database)
    env.cr.execute("SELECT name FROM ir_module_module WHERE state='installed' AND name IN ('payroll','step_payroll_oca_api') ORDER BY name")
    require(env.cr.fetchall() == [('payroll',), ('step_payroll_oca_api',)], 'actual-community-engine-required')
    env.cr.execute("SELECT count(*) FROM ir_module_module WHERE license='OEEL-1' AND state IN ('installed','to install','to upgrade','to remove')")
    require(env.cr.fetchone() == (0,), 'zero-enterprise-target-required')
    inspect_oca_benefit_boundary(env)
    target = _source_facts(env.cr, source_plan.type_ids, expected_database=expected_database)
    require((target.field_rows, target.family_rows, target.inbound_rows)
        == (source_plan.field_rows, source_plan.family_rows, source_plan.inbound_rows),
        'anchored-native-family-or-inbound-identities-differ')
    return dict(mode=mode, type_ids=list(source_plan.type_ids), family_tables=len(FAMILY_TABLES),
        family_rows=sum(row[1] for row in target.family_rows), family_hashes_exact=True,
        inbound_id_hashes_exact=True, configuration_data_cohort_admissible=True,
        salary_benefits_ids_implemented=False, native_benefit_engine_implemented=False,
        native_benefit_scope_compatible=False, integral_conversion=False,
        functional_payroll_certified=False, original_identity_adopted=False,
        database_writes=False, model_aliases_created=False)
