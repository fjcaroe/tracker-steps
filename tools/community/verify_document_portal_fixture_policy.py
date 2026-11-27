"""Compare a pre-provisioned private portal fixture with its original sealed authorization policy."""
import argparse
import fcntl
import json
import re

import psycopg2
from psycopg2 import sql


RELATIONS = {
    "res_users": ("id",), "res_groups": ("id",), "res_groups_users_rel": ("gid", "uid"),
    "res_groups_implied_rel": ("gid", "hid"), "rule_group_rel": ("rule_group_id", "group_id"),
    "ir_model_access": ("id",), "ir_rule": ("id",), "documents_document": ("id",),
    "documents_access": ("id",), "mail_mail": ("id",),
}


def policy(cursor, highest_original_uid):
    result = {}
    for name, keys in RELATIONS.items():
        column = {"res_users": "id", "res_groups_users_rel": "uid"}.get(name)
        where = sql.SQL("WHERE {} <= %s").format(sql.Identifier(column)) if column else sql.SQL("")
        cursor.execute(sql.SQL("""
            SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t)::text, chr(10)
                   ORDER BY {}),''),'UTF8')),'hex') FROM {} t {}
        """).format(sql.SQL(",").join(map(sql.Identifier, keys)), sql.Identifier(name), where),
                       (highest_original_uid,) if column else ())
        result[name] = list(cursor.fetchone())
    cursor.execute("""
        SELECT n.nspname, c.relname, t.tgname, pg_get_triggerdef(t.oid), t.tgenabled
          FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2,3
    """)
    triggers = cursor.fetchall()
    assert any(t[1:3] == ("res_groups_users_rel", "steps_sys_policy_row") and t[4] == "O" for t in triggers)
    return result, triggers


def verify(source, target):
    if not re.fullmatch(r"COMMUNITY_PORTAL_SYS_[A-Z0-9]+", source) or target != source + "A":
        raise ValueError("A private, separately provisioned portal copy is required")
    with psycopg2.connect(dbname=source) as original, psycopg2.connect(dbname=target) as candidate:
        original.set_session(readonly=True, isolation_level="REPEATABLE READ")
        candidate.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with original.cursor() as control, candidate.cursor() as check:
            control.execute("SELECT max(id) FROM res_users")
            high, = control.fetchone()
            base, all_triggers = policy(control, high)
            current, target_triggers = policy(check, high)
            if current != base or target_triggers != all_triggers:
                raise ValueError("Original users, rules, memberships, document rows or trigger definitions differ")
            check.execute("""
                SELECT count(*), bool_and(u.active AND u.share AND u.login LIKE 'community-portal-%%' AND EXISTS (
                     SELECT 1 FROM res_groups_users_rel g JOIN ir_model_data m ON m.res_id=g.gid
                      WHERE g.uid=u.id AND m.model='res.groups' AND m.module='base' AND m.name='group_portal')
                     AND NOT EXISTS (SELECT 1 FROM res_groups_users_rel g JOIN ir_model_data m ON m.res_id=g.gid
                      WHERE g.uid=u.id AND m.model='res.groups' AND m.module='base'
                        AND m.name IN ('group_user','group_system')))
                  FROM res_users u WHERE u.id>%s
            """, (high,))
            if check.fetchone() != (2, True):
                raise ValueError("Expected exactly two new external recipients with ordinary portal membership")
            check.execute("SELECT count(*) FROM ir_module_module WHERE state='installed' AND license='OEEL-1'")
            if check.fetchone() != (0,):
                raise ValueError("Expected a Community-only fixture")
    return {"source": source, "target": target, "new_external_accounts": 2, "enterprise": 0,
            "identical_triggers": len(all_triggers), "original_rows": {k: v[0] for k, v in base.items()},
            "all_original_policy_and_document_hashes_match": True}


if __name__ == "__main__":
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("source")
    command.add_argument("target")
    arguments = command.parse_args()
    with open("/run/lock/steps-environments.lock", "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        print(json.dumps(verify(arguments.source, arguments.target)))
