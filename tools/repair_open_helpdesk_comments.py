#!/usr/bin/env python3
"""One-time, reversible formatting repair for legacy open helpdesk notes.

Run on the Odoo host with its Python environment. Defaults to a read-only preview.
Use --apply to back up original mail_message bodies and update only their HTML.
"""

import argparse
import configparser
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import psycopg2


DB_NAME = "karo_consultorias"
BACKUP_ROOT = Path("/opt/backups/odoo/2026-09-28-support-open-comments")
ESCAPED_BREAK = re.compile(r"&lt;br\s*/?&gt;", re.IGNORECASE)
REAL_BREAK = re.compile(r"<br\s*/?>", re.IGNORECASE)
NUMBERED = re.compile(r"^\d+[.)]\s+")
BULLET = re.compile(r"^[-•]\s+")
HEADING = re.compile(r"^[A-ZÁÉÍÓÚÜÑ0-9 /()–—+.,-]{3,100}$")
LABEL = re.compile(r"^([A-ZÁÉÍÓÚÜÑ0-9 /()–—+.,-]{3,100}:)(\s*.*)$")


def rendered_lines(markup):
    markup = ESCAPED_BREAK.sub("\n", markup)
    markup = REAL_BREAK.sub("\n", markup)
    markup = re.sub(r"</(?:p|li|h[1-6])>", "\n", markup, flags=re.I)
    markup = re.sub(r"<[^>]+>", "", markup)
    return [html.unescape(line).strip() for line in markup.splitlines() if line.strip()]


def content_lines(lines):
    return [NUMBERED.sub("", BULLET.sub("", line)) for line in lines]


def reformat(body):
    if not (body.startswith("<p>") and body.endswith("</p>")):
        raise ValueError("unexpected message wrapper")
    inner = body[3:-4]
    inner = ESCAPED_BREAK.sub("\n", inner)
    inner = REAL_BREAK.sub("\n", inner)
    if "<br" in inner.lower() or "&lt;br" in inner.lower():
        raise ValueError("unrecognized line break")

    result = []
    list_kind = None
    first = True

    def close_list():
        nonlocal list_kind
        if list_kind:
            result.append(f"</{list_kind}>")
            list_kind = None

    for raw in inner.split("\n"):
        line = raw.strip()
        if not line:
            close_list()
            continue
        kind = "ul" if BULLET.match(line) else "ol" if NUMBERED.match(line) else None
        if kind:
            if list_kind != kind:
                close_list()
                result.append(f"<{kind}>")
                list_kind = kind
            item = BULLET.sub("", line) if kind == "ul" else NUMBERED.sub("", line)
            result.append(f"<li>{item}</li>")
            continue
        close_list()
        if first:
            result.append(f"<p><strong>{line}</strong></p>")
            first = False
        elif HEADING.fullmatch(html.unescape(line)) and len(line) <= 100:
            result.append(f"<h4>{line}</h4>")
        elif match := LABEL.match(line):
            result.append(f"<p><strong>{match.group(1)}</strong>{match.group(2)}</p>")
        else:
            result.append(f"<p>{line}</p>")
    close_list()
    formatted = "\n".join(result)
    before = content_lines(rendered_lines(body))
    after = content_lines(rendered_lines(formatted))
    if before != after:
        raise ValueError(f"visible content changed: {before!r} != {after!r}")
    return formatted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read("/etc/odoo18.conf")
    options = config["options"]
    connection = {"dbname": DB_NAME}
    for source, target in (("db_host", "host"), ("db_port", "port"),
                           ("db_user", "user"), ("db_password", "password")):
        value = options.get(source)
        if value and value.lower() != "false":
            connection[target] = value
    conn = psycopg2.connect(**connection)
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT m.id, t.id, m.body
                FROM mail_message m
                JOIN helpdesk_ticket t ON t.id = m.res_id AND m.model = 'helpdesk.ticket'
                JOIN helpdesk_stage s ON s.id = t.stage_id
                WHERE s.fold IS NOT TRUE
                  AND (m.body ILIKE '%%&lt;br%%' OR m.id IN (8742, 8744))
                ORDER BY t.id, m.id
                FOR UPDATE OF m
            """)
            rows = cursor.fetchall()
            changes = [(mid, tid, body, reformat(body)) for mid, tid, body in rows]
            print(json.dumps({"tickets": sorted({tid for _, tid, _, _ in changes}),
                              "message_ids": [mid for mid, _, _, _ in changes],
                              "count": len(changes), "apply": args.apply}))
            if not args.apply:
                conn.rollback()
                return
            if len(changes) != 19 or sorted({tid for _, tid, _, _ in changes}) != [16, 22, 27, 28, 30]:
                raise ValueError("ticket or message count changed since audit")
            BACKUP_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
            backup = BACKUP_ROOT / "mail_message_before.json"
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"created_at": datetime.now(timezone.utc).isoformat(),
                           "database": DB_NAME,
                           "messages": [{"id": mid, "ticket_id": tid, "body": body}
                                        for mid, tid, body, _ in changes]}, stream,
                          ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            for mid, _, before, after in changes:
                cursor.execute("UPDATE mail_message SET body=%s WHERE id=%s AND body=%s",
                               (after, mid, before))
                if cursor.rowcount != 1:
                    raise ValueError(f"concurrent modification of message {mid}")
            conn.commit()
            print(f"Updated {len(changes)} messages; backup: {backup}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
