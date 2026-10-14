"""Post an Odoo Helpdesk internal note with rendered HTML over XML-RPC.

Example:
    python scripts/post_helpdesk_note.py 35 --html-file note.html --attachment evidence.pdf

Credentials are read from ~/.odoo/helpdesk_api.json (or --config); they are
never printed or stored in the repository.
"""

import argparse
import base64
import json
import mimetypes
import re
import xmlrpc.client
from pathlib import Path


def connect(config_path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    url = config["url"].rstrip("/")
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(config["db"], config["username"], config["api_key"], {})
    if not uid:
        raise RuntimeError("No fue posible autenticar en Helpdesk")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return config, uid, models


def execute(config, uid, models, model, method, args, kwargs=None):
    return models.execute_kw(
        config["db"], uid, config["api_key"], model, method, args, kwargs or {}
    )


def post_note(config, uid, models, ticket_id, body, attachment_paths=()):
    ticket = execute(
        config, uid, models, "helpdesk.ticket", "read", [[ticket_id]],
        {"fields": ["name"]},
    )
    if not ticket:
        raise ValueError(f"No existe el ticket {ticket_id}")

    if not body.strip():
        raise ValueError("La nota está vacía")
    if re.match(r"\s*&lt;[a-z]", body, re.I):
        raise ValueError("La nota parece contener HTML ya escapado")

    attachment_ids = []
    for path in attachment_paths:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        attachment_id = execute(
            config, uid, models, "ir.attachment", "create", [{
                "name": path.name,
                "type": "binary",
                "datas": base64.b64encode(path.read_bytes()).decode("ascii"),
                "mimetype": mime,
                "res_model": "helpdesk.ticket",
                "res_id": ticket_id,
            }],
        )
        attachment_ids.append(attachment_id)

    message_id = execute(
        config, uid, models, "helpdesk.ticket", "message_post", [[ticket_id]],
        {
            "body": body,
            "body_is_html": True,  # Odoo 18 otherwise escapes XML-RPC strings.
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_note",
            "attachment_ids": attachment_ids,
        },
    )
    message = execute(
        config, uid, models, "mail.message", "read", [[message_id]],
        {"fields": ["model", "res_id", "body", "attachment_ids"]},
    )[0]
    if message["model"] != "helpdesk.ticket" or message["res_id"] != ticket_id:
        raise RuntimeError("La nota no quedó asociada al ticket solicitado")
    first_tag = re.match(r"\s*<([a-z][\w-]*)\b", body, re.I)
    if first_tag and not re.search(rf"<{re.escape(first_tag.group(1))}\b", message["body"], re.I):
        raise RuntimeError("La nota se publicó, pero el HTML no quedó renderizable")
    if not set(attachment_ids).issubset(set(message["attachment_ids"])):
        raise RuntimeError("La nota se publicó, pero faltan adjuntos")
    return message_id, attachment_ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticket_id", type=int)
    parser.add_argument("--html-file", required=True, type=Path)
    parser.add_argument("--attachment", action="append", type=Path, default=[])
    parser.add_argument("--config", type=Path, default=Path.home() / ".odoo" / "helpdesk_api.json")
    args = parser.parse_args()
    body = args.html_file.read_text(encoding="utf-8")
    config, uid, models = connect(args.config)
    message_id, attachment_ids = post_note(
        config, uid, models, args.ticket_id, body, args.attachment
    )
    print(f"NOTA_OK ticket={args.ticket_id} mensaje={message_id} adjuntos={attachment_ids}")


if __name__ == "__main__":
    main()
