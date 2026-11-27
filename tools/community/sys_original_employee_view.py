"""Keep the original SyS public directory projection when its optional apps are outside this registry."""

import hashlib


FIELDS = (
    ("hr.employee", "last_appraisal_id", 21008, "hr_appraisal"),
    ("hr.employee", "ongoing_appraisal_count", 21013, "hr_appraisal"),
    ("hr.employee", "timesheet_manager_id", 14761, "timesheet_grid"),
    ("hr.employee.public", "last_appraisal_id", 21023, "hr_appraisal"),
    ("hr.employee.public", "ongoing_appraisal_count", 21025, "hr_appraisal"),
    ("hr.employee.public", "timesheet_manager_id", 14763, "timesheet_grid"),
)


def keep_existing_directory(model):
    cr = model.env.cr
    cr.execute("""SELECT f.model,f.name,f.id,d.module FROM ir_model_fields f JOIN ir_model_data d
        ON d.model='ir.model.fields' AND d.res_id=f.id AND d.name='field_'||replace(f.model,'.','_')||'__'||f.name
        WHERE f.model IN ('hr.employee','hr.employee.public') AND f.name IN
        ('last_appraisal_id','ongoing_appraisal_count','timesheet_manager_id')
        AND d.module IN ('hr_appraisal','timesheet_grid') ORDER BY f.model,f.name""")
    if tuple(cr.fetchall()) != FIELDS:
        return False
    cr.execute("""SELECT pg_get_viewdef(c.oid,false),c.relkind,pg_get_userbyid(c.relowner),c.relacl,c.reloptions,
        ARRAY(SELECT a.attname FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
              ORDER BY a.attnum)
        FROM pg_class c WHERE c.oid=to_regclass('public.hr_employee_public')""")
    row = cr.fetchone()
    if not row or row[1:5] != ("v", "odoo", None, None) or hashlib.sha256(row[0].encode()).hexdigest() != (
            "0bd3f2b26fe7b0d1345b4a69e04c7fd98310e7de57b166e0e085aec218ae219d"):
        raise ValueError("The original SyS public employee view must match its admitted definition")
    original = {"emp." + name for name in row[5]}
    requested = set(model._get_fields().split(","))
    optional = {"emp." + name for owner, name, _, _ in FIELDS if owner == "hr.employee.public"}
    if not requested <= original or not original - requested <= optional:
        raise ValueError("The current HR registry needs a new public employee view projection")
    return True
