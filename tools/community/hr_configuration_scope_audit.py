"""Read the private configuration storage/security contract without salary code."""
import argparse
import json
import os
from pathlib import Path
import re

from psycopg2 import sql
from validate_payroll_relation_storage import connect


MODELS = {
    "hr.payroll.structure": ("hr_payroll_structure", ("company_id", "country_id", "parent_id", "type_id", "rule_ids", "input_line_type_ids")),
    "hr.salary.rule": ("hr_salary_rule", ("company_id", "country_id", "struct_id", "category_id", "parent_rule_id", "active")),
    "hr.salary.rule.category": ("hr_salary_rule_category", ("company_id", "country_id", "parent_id")),
    "hr.payroll.structure.type": ("hr_payroll_structure_type", ("company_id", "country_id", "default_struct_id", "default_work_entry_type_id")),
    "hr.payslip.input.type": ("hr_payslip_input_type", ("company_id", "country_id", "struct_ids", "active")),
}


def inspect_sql(cursor):
    cursor.execute("SHOW transaction_read_only")
    assert cursor.fetchone()[0] == "on"
    result = {"models": {}, "read_only": True, "salary_formulas_read": False, "orm_loaded": False}
    for model, (table, names) in MODELS.items():
        cursor.execute("SELECT attname,attnotnull FROM pg_attribute WHERE attrelid=to_regclass(%s) AND attnum>0 AND NOT attisdropped", (table,))
        columns = dict(cursor.fetchall())
        cursor.execute("""SELECT id,name,ttype,relation,required,readonly,store,related,on_delete
            FROM ir_model_fields WHERE model=%s AND name=ANY(%s) ORDER BY name""", (model, list(names)))
        fields = [dict(zip(("id", "name", "type", "relation", "required", "readonly", "store", "related", "on_delete"), row))
                  for row in cursor.fetchall()]
        selected = [name for name in ("id", "code", *names) if name in columns]
        cursor.execute(sql.SQL("SELECT {} FROM {} ORDER BY id").format(
            sql.SQL(",").join(map(sql.Identifier, selected)), sql.Identifier(table)))
        rows = [dict(zip(selected, row)) for row in cursor.fetchall()]
        result["models"][model] = {"table": table, "fields": fields, "rows": rows,
            "columns_not_null": {name: columns[name] for name in names if name in columns}}
    cursor.execute("""SELECT a.id,m.model,a.group_id,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink,a.active
        FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
        WHERE m.model=ANY(%s) ORDER BY m.model,a.id""", (list(MODELS),))
    result["acl"] = [dict(zip(("id", "model", "group_id", "read", "write", "create", "unlink", "active"), row)) for row in cursor.fetchall()]
    cursor.execute("""SELECT r.id,m.model,r.domain_force,r.perm_read,r.perm_write,r.perm_create,r.perm_unlink,r.active
        FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
        WHERE m.model=ANY(%s) ORDER BY m.model,r.id""", (list(MODELS),))
    result["rules"] = [dict(zip(("id", "model", "domain", "read", "write", "create", "unlink", "active"), row)) for row in cursor.fetchall()]
    cursor.execute("""SELECT rel.rule_group_id,rel.group_id FROM rule_group_rel rel JOIN ir_rule r ON r.id=rel.rule_group_id
        JOIN ir_model m ON m.id=r.model_id WHERE m.model=ANY(%s) ORDER BY rel.rule_group_id,rel.group_id""", (list(MODELS),))
    result["rule_groups"] = [list(row) for row in cursor.fetchall()]
    cursor.execute("""SELECT module,name,model,res_id FROM ir_model_data
        WHERE model=ANY(%s) ORDER BY module,name""", (list(MODELS),))
    result["xmlids"] = [dict(zip(("module", "name", "model", "id"), row)) for row in cursor.fetchall()]
    cursor.execute("""SELECT conrelid::regclass::text,conname,pg_get_constraintdef(oid),convalidated
        FROM pg_constraint WHERE conrelid=ANY(%s::regclass[]) ORDER BY conrelid::regclass::text,conname""",
        ([value[0] for value in MODELS.values()],))
    result["constraints"] = [dict(zip(("table", "name", "definition", "validated"), row)) for row in cursor.fetchall()]
    return result


def inspect_registry(env):
    """Only inspect loaded classes/field descriptors; never access model records."""
    env.cr.execute("SHOW transaction_read_only")
    assert env.cr.fetchone()[0] == "on"
    result = {"models": {}, "read_only": True, "orm_records_read": False, "provider_methods_called": False}
    for name, (table, names) in MODELS.items():
        model = env.registry.models[name]
        result["models"][name] = {field: {attr: getattr(model._fields[field], attr, None) for attr in
            ("type", "comodel_name", "required", "readonly", "store", "related", "ondelete", "groups")}
            for field in names if field in model._fields}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    assert re.fullmatch(r"(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+", args.database)
    assert str(args.output.resolve()).startswith("/opt/steps-validation/") and not args.output.exists()
    with connect(args.database) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cursor:
            result = inspect_sql(cursor)
    args.output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print("HR_CONFIGURATION_SCOPE_AUDIT " + args.database + " " + str({name: len(value["rows"]) for name, value in result["models"].items()}))


if __name__ == "__main__":
    main()
