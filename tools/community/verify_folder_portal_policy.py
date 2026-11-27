"""Verify the original SyS access policy on the private Community portal folder derivative."""
import fcntl
import json

import psycopg2
from psycopg2 import sql


ORIGINAL = "COMMUNITY_PORTAL_SYS_20261126U41P"
FOLDERS = "COMMUNITY_PORTAL_SYS_20261126U41PF"
TABLES = {
    "res_groups": ("id",), "res_users": ("id",), "res_groups_users_rel": ("gid", "uid"),
    "res_groups_implied_rel": ("gid", "hid"), "rule_group_rel": ("rule_group_id", "group_id"),
    "ir_model_access": ("id",), "ir_rule": ("id",), "documents_document": ("id",),
    "documents_access": ("id",), "mail_mail": ("id",),
}


def catalog(cursor, high_user, new_acl=None):
    result = {}
    for name, keys in TABLES.items():
        body = sql.SQL("to_jsonb(t)")
        where, params = sql.SQL(""), []
        if name == "documents_document":
            body = sql.SQL("to_jsonb(t)-'step_portal_reference_prefix'-'step_portal_reference_suffix'")
        elif name in ("res_users", "res_groups_users_rel"):
            column = "id" if name == "res_users" else "uid"
            where, params = sql.SQL("WHERE {}<=%s").format(sql.Identifier(column)), [high_user]
        elif name == "ir_model_access":
            # Re-importing Odoo's ACL CSV updates its audit stamps. Compare the complete ACL policy.
            body = sql.SQL("to_jsonb(t)-'write_uid'-'write_date'")
            if new_acl is not None:
                where, params = sql.SQL("WHERE id<>%s"), [new_acl]
        cursor.execute(sql.SQL("""
            SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(({})::text,chr(10)
               ORDER BY {}),''),'UTF8')),'hex') FROM {} t {}
        """).format(body, sql.SQL(",").join(map(sql.Identifier, keys)), sql.Identifier(name), where), params)
        result[name] = cursor.fetchone()
    cursor.execute("""
        SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled
          FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
         WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY 1,2,3
    """)
    return result, cursor.fetchall()


def verify():
    with psycopg2.connect(dbname=ORIGINAL) as db, psycopg2.connect(dbname=FOLDERS) as clone:
        for cp in (db, clone):
            cp.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with db.cursor() as src, clone.cursor() as dst:
            src.execute("SELECT max(id) FROM res_users")
            highest, = src.fetchone()
            dst.execute("""
                SELECT a.id,m.model,g.module,g.name,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink
                  FROM ir_model_data x JOIN ir_model_access a ON a.id=x.res_id JOIN ir_model m ON m.id=a.model_id
                  JOIN ir_model_data g ON g.res_id=a.group_id AND g.model='res.groups' AND g.module='base'
                 WHERE x.module='step_document_library_portal' AND x.name='access_reference_wizard'
                       AND x.model='ir.model.access'
            """)
            acl, = dst.fetchall()
            assert acl[1:] == ("step.document.library.reference", "base", "group_user", True, True, True, True)
            original, triggers = catalog(src, highest)
            current, new_triggers = catalog(dst, highest, acl[0])
            assert original == current and new_triggers == triggers
            assert any(x[1:3] == ("res_groups_users_rel", "steps_sys_policy_row") and x[4] == "O" for x in triggers)
            dst.execute("""
                SELECT count(*),bool_and(u.active AND u.share AND u.login LIKE 'community-portal-%%'
                     AND EXISTS(SELECT 1 FROM res_groups_users_rel r JOIN ir_model_data g ON g.res_id=r.gid
                         WHERE r.uid=u.id AND g.model='res.groups' AND g.module='base' AND g.name='group_portal')
                     AND NOT EXISTS(SELECT 1 FROM res_groups_users_rel r JOIN ir_model_data g ON g.res_id=r.gid
                         WHERE r.uid=u.id AND g.model='res.groups' AND g.module='base'
                           AND g.name IN ('group_user','group_system')))
                 FROM res_users u WHERE u.id>%s
            """, [highest])
            assert dst.fetchone() == (2, True)
            return {"original_counts": {k: v[0] for k, v in original.items()}, "identical_triggers": len(triggers),
                    "temporary_portal_accounts": 2, "additional_internal_clipboard_acl": 1,
                    "original_policies_documents_and_mail_match": True}


if __name__ == "__main__":
    with open("/run/lock/steps-environments.lock", "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        print(json.dumps(verify()))

