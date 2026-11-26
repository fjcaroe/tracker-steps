"""Admit OCA's new optional line parent and expose SyS's one primary rule owner."""
import re

from preflight_original_history_storage import require


def prepare(cr, database):
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', database),
            'private SyS cohort required')
    cr.execute('SELECT current_database()')
    require(cr.fetchone() == (database,), 'SyS connection mismatch')
    cr.execute("""SELECT count(*) FROM pg_trigger WHERE tgname='steps_sys_history_guard_row'
                  AND tgenabled='O' AND NOT tgisinternal""")
    require(cr.fetchone() == (4,), 'SyS closed history must be guarded')
    cr.execute("""SELECT ttype,relation,relation_field,required,store FROM ir_model_fields
                  WHERE model='hr.payroll.structure' AND name='rule_ids'""")
    require(cr.fetchone() == ('one2many', 'hr.salary.rule', 'struct_id', False, True),
            'SyS rule_ids source contract mismatch')
    cr.execute("""SELECT ttype,related,store FROM ir_model_fields WHERE model='hr.payslip'
                  AND name='journal_id'""")
    require(cr.fetchone() == ('many2one', 'struct_id.journal_id', False), 'SyS payslip journal drift')
    cr.execute("""SELECT count(*),count(r.struct_id),count(s.id) FROM hr_salary_rule r
                  LEFT JOIN hr_payroll_structure s ON s.id=r.struct_id""")
    total, owned, valid = cr.fetchone()
    require(total and total == owned == valid, 'SyS original rule owner unresolved')
    cr.execute("""SELECT count(*) FROM ir_model_fields WHERE model='hr.payslip.line' AND name='parent_line_id'""")
    require(cr.fetchone() == (0,), 'Unexpected native SyS line parent')
    cr.execute("""SELECT c.relkind FROM pg_class c WHERE oid=to_regclass('public.hr_structure_salary_rule_rel')""")
    require(cr.fetchone() is None, 'SyS ownership projection already exists')
    cr.execute("""CREATE VIEW public.hr_structure_salary_rule_rel AS
                  SELECT struct_id,id AS rule_id FROM public.hr_salary_rule WHERE struct_id IS NOT NULL OFFSET 0""")
    # A non-updatable view keeps existing adapter SQL readers synchronized
    # with the real primary FK, including newly created or moved rules.
    cr.execute("""SELECT is_updatable FROM information_schema.views
                  WHERE table_schema='public' AND table_name='hr_structure_salary_rule_rel'""")
    require(cr.fetchone() == ('NO',), 'SyS rule projection must be read-only')
    cr.execute('SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid=\'public.hr_salary_rule\'::regclass')
    owner = cr.fetchone()[0]
    from psycopg2 import sql
    cr.execute(sql.SQL("ALTER VIEW public.hr_structure_salary_rule_rel OWNER TO {}").format(sql.Identifier(owner)))
    cr.execute('SELECT COUNT(*) FROM hr_structure_salary_rule_rel')
    require(cr.fetchone() == (total,), 'SyS rule ownership projection drift')
    # Creating a missing stored compute during Odoo init would schedule a
    # write_date/write_uid update across otherwise unchanged, closed lines.
    cr.execute('ALTER TABLE public.hr_payslip_line ADD COLUMN parent_line_id integer')
    cr.execute('SELECT count(*),count(parent_line_id) FROM hr_payslip_line')
    lines, parents = cr.fetchone()
    require(lines and parents == 0, 'SyS historical line parents must remain unrecorded')
    return {'salary_rules': total, 'lines': lines, 'non_null_parent': parents}
