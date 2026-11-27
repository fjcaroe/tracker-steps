"""Compare complete rows from the sealed PostgreSQL COPY records with post-install registry records."""
import gzip
import io
import json
import re
import sys

import psycopg2
from psycopg2 import sql

from check_local_fiscal_print import DB, WORK, SOCKET, PORT


TABLES = ("ir_module_module", "ir_module_module_dependency", "ir_model_data", "ir_cron_trigger", "ir_ui_view",
          "ir_attachment")


def inspect():
    frozen = json.loads(gzip.decompress((WORK / "source-snapshot.json.gz").read_bytes()))
    rows = {}
    with psycopg2.connect(dbname=DB, user="postgres", host=SOCKET, port=PORT) as conn, conn.cursor() as cr:
        cr.execute("SET LOCAL search_path=pg_catalog,public")
        cr.execute("SET LOCAL TIME ZONE 'UTC'")
        source = sys.stdin.buffer
        for line in source:
            if not line.startswith(b"COPY "):
                continue
            match = re.fullmatch(rb"COPY public\.([a-z_]+) \(([^)]+)\) FROM stdin;\s*", line)
            if not match:
                raise ValueError("Unexpected SQL COPY input")
            table = match[1].decode()
            if table not in TABLES or table in rows:
                raise ValueError("Unexpected COPY table")
            fields = match[2].decode().split(", ")
            cr.execute(sql.SQL("CREATE TEMPORARY TABLE ref (LIKE public.{}) ON COMMIT DROP").format(sql.Identifier(table)))
            copy = io.BytesIO()
            for line in source:
                if line in (b"\\.\n", b"\\.\r\n"):
                    break
                copy.write(line)
            copy.seek(0)
            cols = sql.SQL(",").join(sql.Identifier(name) for name in fields)
            cr.copy_expert(sql.SQL("COPY pg_temp.ref ({}) FROM STDIN").format(cols), copy)
            cr.execute("""SELECT count(*),encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex')
                          FROM (SELECT encode(sha256(convert_to(to_jsonb(r)::text,'UTF8')),'hex') h FROM pg_temp.ref r) t""")
            if list(cr.fetchone()) != frozen["public_tables"][table]:
                raise ValueError("Table baseline differs: " + table)
            cr.execute(sql.SQL("""SELECT count(*) FILTER (WHERE a.id IS NULL),count(*) FILTER (WHERE b.id IS NULL),
                          count(*) FILTER (WHERE a.id IS NOT NULL AND b.id IS NOT NULL AND to_jsonb(a)<>to_jsonb(b))
                          FROM pg_temp.ref a FULL JOIN public.{} b USING(id)""").format(sql.Identifier(table)))
            added, deleted, changed = cr.fetchone()
            cr.execute(sql.SQL("""SELECT k,count(*) FROM pg_temp.ref a JOIN public.{} b USING(id)
                          CROSS JOIN LATERAL jsonb_object_keys(to_jsonb(a)) k WHERE to_jsonb(a)<>to_jsonb(b)
                          AND (to_jsonb(a)->k) IS DISTINCT FROM (to_jsonb(b)->k) GROUP BY k ORDER BY k""").format(sql.Identifier(table)))
            differences = dict(cr.fetchall())
            cr.execute(sql.SQL("""SELECT a.id FROM pg_temp.ref a JOIN public.{} b USING(id) WHERE to_jsonb(a)<>to_jsonb(b)
                          ORDER BY a.id LIMIT 20""").format(sql.Identifier(table)))
            ids = [r[0] for r in cr.fetchall()]
            rows[table] = {"added": added, "deleted": deleted, "changed": changed, "columns": differences,
                           "first_changed_ids": ids}
            if table == "ir_attachment":
                for label, relations in (("removed_caches", ("pg_temp.ref", "public.ir_attachment")),
                                         ("added_caches", ("public.ir_attachment", "pg_temp.ref"))):
                    a, b = (sql.Identifier(*value.split(".")) for value in relations)
                    cr.execute(sql.SQL("""SELECT a.name,a.mimetype,a.res_model,a.res_id,a.url FROM {} a
                                 LEFT JOIN {} b ON b.id=a.id WHERE b.id IS NULL ORDER BY a.name""").format(a, b))
                    values = cr.fetchall()
                    if any(mime != "text/css" or model != "ir.ui.view" or record or
                           not re.fullmatch(r"/web/assets/[a-f0-9]+/web[.]report_assets_(common|pdf)[.]min[.]css", url)
                           or not url.endswith("/" + name) for name, mime, model, record, url in values):
                        raise ValueError("A non-cache attachment was affected")
                    rows[table][label] = [v[0] for v in values]
            cr.execute("DROP TABLE pg_temp.ref")
    if rows.keys() != set(TABLES):
        raise ValueError("Incomplete metadata table coverage")
    print(json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    inspect()
