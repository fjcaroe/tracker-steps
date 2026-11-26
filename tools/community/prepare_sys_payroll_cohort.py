"""Prepare the original SyS payroll identities on a disposable startup derivative.

Use this only for a scoped Previred experiment after recording a complete
graph refusal. The native reference and the all-module derivative are kept.
The lock is held by the restore/install coordinator for the entire operation.
"""
import re

from admit_sys_payroll_storage import related_identity
from preflight_original_history_storage import require
from sys_previred_preservation import identifier
from prepare_sys_structure_storage import prepare as prepare_structure_storage
from sys_cohort_required import inventory as required_inventory


PAYROLL = {'step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_previred_corrections',
           'step_hr_previred_movement_dates', 'l10n_cl_simpledigital_payroll'}
PROTECTED = {
    'ir_model_data': ('id', 'module', 'name', 'model', 'res_id', 'noupdate'),
    'ir_model': ('id', 'model', 'state'),
    'ir_model_fields': ('id', 'model', 'name', 'state'),
    'ir_model_fields_selection': ('id', 'field_id', 'value'),
    'ir_act_report_xml': ('id', 'model', 'binding_model_id'),
    'ir_model_access': None, 'ir_rule': None, 'res_groups': None,
    'hr_salary_rule': None, 'hr_salary_rule_category': None, 'hr_payslip_input_type': None,
    'hr_payroll_structure': None, 'hr_payroll_structure_type': None,
}


def preserve_ids(cr, table, keys):
    rel = 'public.' + identifier(table)
    cr.execute(f'SELECT max(id),count(*) FROM {rel}')
    last, count = cr.fetchone()
    require(last and count, 'sys-cohort-empty-original-master:' + table)
    if keys is None:
        cr.execute('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 '
                   'AND NOT attisdropped ORDER BY attnum', (rel,))
        keys = [row[0] for row in cr.fetchall()]
    names = ','.join("'" + identifier(k).strip('"') + "'" for k in keys)
    related_guard = ''
    if table == 'ir_model_fields':
        related_ids = ','.join(str(int(pk)) for pk in related_identity(cr).values())
        related_guard = f"""
        IF OLD.id IN ({related_ids}) AND
           ROW(OLD.ttype,OLD.related,OLD.store,OLD.required,OLD.relation,OLD.readonly)
           IS DISTINCT FROM ROW(NEW.ttype,NEW.related,NEW.store,NEW.required,NEW.relation,NEW.readonly)
        THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS related field identity changed';
        END IF;
"""
    # IDs below the old allocator high-water mark are reserved throughout the
    # loader rehearsal. New columns may be initialized independently.
    body = f"""
DECLARE prev jsonb; next jsonb;
BEGIN
    IF TG_OP = 'TRUNCATE' THEN
        RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS protected identity truncate: {table}';
    END IF;
    IF TG_OP <> 'INSERT' AND OLD.id <= {last} THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS protected identity delete: {table}';
        END IF;
        {related_guard}
        prev := to_jsonb(OLD); next := to_jsonb(NEW);
        IF EXISTS (SELECT 1 FROM unnest(ARRAY[{names}]) AS x(k)
                   WHERE prev -> x.k IS DISTINCT FROM next -> x.k) THEN
            RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS protected identity update: {table}';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    IF NEW.id <= {last} THEN
        RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS protected identity insert: {table}';
    END IF;
    RETURN NEW;
END
"""
    fn = 'public.' + identifier('steps_sys_identity_' + table)
    cr.execute(f'CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS %s',
               (body,))
    cr.execute(f'CREATE TRIGGER steps_sys_identity_row BEFORE INSERT OR UPDATE OR DELETE ON {rel} '
               f'FOR EACH ROW EXECUTE PROCEDURE {fn}()')
    cr.execute(f'CREATE TRIGGER steps_sys_identity_truncate BEFORE TRUNCATE ON {rel} '
               f'FOR EACH STATEMENT EXECUTE PROCEDURE {fn}()')
    return {'max_id': last, 'rows': count, 'columns': list(keys)}


def prepare(cr, database, graph):
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', database),
            'sys-cohort-new-private-database-required')
    cr.execute('SELECT current_database()')
    require(cr.fetchone() == (database,), 'sys-cohort-wrong-connection')
    require(graph['full_source_graph_resolved'] is False and not graph['candidate_engine_missing']
            and all(graph['previred_graph'].get(n) for n in PAYROLL), 'sys-cohort-previred-closure-incomplete')
    cr.execute("SELECT name FROM ir_module_module WHERE state='installed' ORDER BY name")
    installed = {row[0] for row in cr.fetchall()}
    excluded = set(graph['missing_installed'])
    require(len(installed) == graph['installed'] and excluded < installed and not PAYROLL & excluded
            and {'hr_payroll', 'hr_payroll_account'} <= excluded, 'sys-cohort-exclusion-drift')
    cr.execute("SELECT name FROM ir_module_module WHERE state='installed' AND license='OEEL-1'")
    # A same-name manifest in Community does not certify the migration of an
    # installed Enterprise package or its consumers (e.g. certificate).
    excluded.update(row[0] for row in cr.fetchall())
    dependencies = graph['resolved_dependencies']
    while True:
        dependents = {name for name, deps in dependencies.items() if set(deps) & excluded}
        if dependents <= excluded:
            break
        excluded.update(dependents)
    require(not (PAYROLL | set(graph['candidate_engine_resolved'])) & excluded,
            'sys-cohort-required-runtime-depends-on-unreviewed-provider')
    excluded &= installed
    cr.execute("SELECT count(*) FROM ir_module_module WHERE state LIKE 'to %'")
    require(cr.fetchone() == (0,), 'sys-cohort-concurrent-module-action')
    cr.execute("SELECT count(*) FROM pg_trigger WHERE tgname='steps_sys_history_guard_row' "
               "AND tgenabled='O' AND NOT tgisinternal")
    require(cr.fetchone() == (4,), 'sys-cohort-closed-history-guards-required')
    guards = {t: preserve_ids(cr, t, keys) for t, keys in PROTECTED.items()}
    # Freeze original actors and record rules. Upstream policy seeds must not
    # widen a native role even when the access row or XML ID itself is intact.
    for table, left, right, owner in (
        ('res_groups_users_rel', 'gid', 'uid', 'res_groups'),
        ('res_groups_implied_rel', 'gid', 'hid', 'res_groups'),
        ('rule_group_rel', 'rule_group_id', 'group_id', 'ir_rule'),
    ):
        rel = 'public.' + identifier(table)
        limit = guards[owner]['max_id']
        fn = 'public.' + identifier('steps_sys_roles_' + table)
        cr.execute(f"""
            CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $pairs$
            BEGIN
                IF TG_OP='TRUNCATE' THEN
                    RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS: truncate original policy';
                END IF;
                IF TG_OP<>'INSERT' AND OLD.{left}<={limit} THEN
                    IF TG_OP='DELETE' OR ROW(NEW.{left},NEW.{right}) IS DISTINCT FROM
                       ROW(OLD.{left},OLD.{right}) THEN
                        RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS: delete or change original policy';
                    END IF;
                END IF;
                IF TG_OP='DELETE' THEN RETURN OLD; END IF;
                IF NEW.{left}<={limit} AND NOT EXISTS(SELECT 1 FROM {rel}
                   WHERE {left}=NEW.{left} AND {right}=NEW.{right}) THEN
                    RAISE EXCEPTION USING ERRCODE='23514', MESSAGE='SyS: add original policy membership';
                END IF;
                RETURN NEW;
            END $pairs$
        """)
        cr.execute(f'CREATE TRIGGER steps_sys_policy_row BEFORE INSERT OR UPDATE OR DELETE ON {rel} '
                   f'FOR EACH ROW EXECUTE PROCEDURE {fn}()')
        cr.execute(f'CREATE TRIGGER steps_sys_policy_truncate BEFORE TRUNCATE ON {rel} '
                   f'FOR EACH STATEMENT EXECUTE PROCEDURE {fn}()')
    # Never put the allocator's current company or parent on an old global master.
    for table, column in (('hr_payroll_structure','company_id'), ('hr_payroll_structure','parent_id'),
                          ('hr_salary_rule','company_id'), ('hr_salary_rule_category','company_id')):
        cr.execute('SELECT format_type(atttypid,atttypmod) FROM pg_attribute WHERE '
                   'attrelid=%s::regclass AND attname=%s AND NOT attisdropped', (table, column))
        found = cr.fetchone()
        if not found:
            cr.execute(f'ALTER TABLE public.{identifier(table)} ADD COLUMN {identifier(column)} integer')
        else:
            require(found == ('integer',), 'sys-cohort-existing-master-column-type')
    rule_storage = prepare_structure_storage(cr, database)
    roles = {}
    for role in ('user', 'manager'):
        native = 'group_hr_payroll_' + role
        target = 'group_payroll_' + role
        cr.execute("SELECT d.res_id FROM ir_model_data d JOIN res_groups g ON g.id=d.res_id WHERE "
                   "d.module='hr_payroll' AND d.name=%s AND d.model='res.groups'", (native,))
        rows = cr.fetchall()
        require(len(rows) == 1, 'sys-cohort-missing-original-role')
        group = rows[0][0]
        cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) "
                   "VALUES('payroll',%s,'res.groups',%s,true) ON CONFLICT(module,name) DO NOTHING", (target,group))
        cr.execute("SELECT model,res_id,noupdate FROM ir_model_data WHERE module='payroll' AND name=%s",(target,))
        require(cr.fetchone() == ('res.groups',group,True), 'sys-cohort-ambiguous-original-role')
        roles[target] = group
    retained = []
    for name, model in (('structure_chile','hr.payroll.structure'),
                        ('structure_type_chile','hr.payroll.structure.type')):
        table = model.replace('.', '_')
        columns = guards[table]['columns']
        selected = ','.join(identifier(k) for k in columns)
        cr.execute("SELECT id,res_id FROM ir_model_data WHERE module='l10n_cl_simpledigital_payroll' "
                   "AND name=%s AND model=%s AND NOT noupdate", (name,model))
        rows = cr.fetchall()
        require(len(rows) == 1, 'sys-cohort-missing-original-supplier-identity')
        xml_pk, res_id = rows[0]
        cr.execute('SELECT md5(to_jsonb(t)::text) FROM (SELECT '+ selected +
                   ' FROM public.' + identifier(table) + ' WHERE id=%s) t',(res_id,))
        checked = cr.fetchone()
        require(checked, 'sys-cohort-original-master-missing')
        retained.append(dict(name=name, model=model, xml_pk=xml_pk, res_id=res_id,
                             columns=columns, original_md5=checked[0]))
    cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE state='installed' AND name=ANY(%s)",
               (sorted(excluded),))
    require(cr.rowcount == len(excluded), 'sys-cohort-concurrent-module-drift')
    return {'database': database, 'structure_storage': rule_storage, 'roles': roles,
            'mandatory_columns': required_inventory(cr), 'retained_supplier_aliases': retained,
            'protected': guards, 'excluded': sorted(excluded),
            'original_graph_database': graph['database'], 'integral_conversion': False}
